"""Offline Marian translation adapter for explicitly provisioned model packs."""

import gc
import hashlib
import json
from collections import OrderedDict
from pathlib import Path

from .ai import TranslationOutput

SUPPORTED_LANGUAGES = frozenset({"tr", "el", "en"})


class LocalMarianTranslator:
    """Lazy local-only loader with bounded input/output and an English pivot."""

    def __init__(
        self,
        model_root: str | Path,
        *,
        max_input_tokens: int = 512,
        max_new_tokens: int = 192,
        max_loaded_models: int = 2,
    ):
        if not 32 <= max_input_tokens <= 1024:
            raise ValueError("max_input_tokens must be 32..1024")
        if not 16 <= max_new_tokens <= 512:
            raise ValueError("max_new_tokens must be 16..512")
        if not 1 <= max_loaded_models <= 4:
            raise ValueError("max_loaded_models must be 1..4")
        self.root = Path(model_root).resolve()
        manifest_path = self.root / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.routes = manifest["routes"]
        required = {"tr-en", "en-tr", "el-en", "en-el"}
        if set(self.routes) != required:
            raise ValueError("Translation manifest must contain exactly four approved routes")
        self.max_input_tokens = max_input_tokens
        self.max_new_tokens = max_new_tokens
        self.max_loaded_models = max_loaded_models
        self._loaded: OrderedDict[str, tuple[object, object]] = OrderedDict()
        self._verified_routes: set[str] = set()

    def _load(self, route: str):
        cached = self._loaded.pop(route, None)
        if cached is not None:
            self._loaded[route] = cached
            return cached
        entry = self.routes[route]
        model_path = (self.root / entry["directory"]).resolve()
        if self.root not in model_path.parents or not model_path.is_dir():
            raise ValueError("Translation model path escapes or is absent from approved root")
        if route not in self._verified_routes:
            weights = (model_path / entry["weights_file"]).resolve()
            if model_path not in weights.parents or not weights.is_file():
                raise ValueError("Translation weights escape or are absent from approved route")
            with weights.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != entry["weights_sha256"]:
                raise ValueError("Translation weights fail recorded SHA-256 verification")
            self._verified_routes.add(route)
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        while len(self._loaded) >= self.max_loaded_models:
            self._loaded.popitem(last=False)
            gc.collect()
        tokenizer = AutoTokenizer.from_pretrained(  # nosec B615
            model_path, local_files_only=True, trust_remote_code=False
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(  # nosec B615
            model_path,
            local_files_only=True,
            trust_remote_code=False,
            weights_only=True,
        )
        model.eval()
        self._loaded[route] = (tokenizer, model)
        return tokenizer, model

    def _direct(self, text: str, source: str, target: str) -> tuple[str, str]:
        import torch

        route = f"{source}-{target}"
        entry = self.routes[route]
        tokenizer, model = self._load(route)
        prefix = entry.get("target_prefix", "")
        encoded = tokenizer(
            prefix + text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_input_tokens,
        )
        with torch.inference_mode():
            tokens = model.generate(
                **encoded,
                max_length=self.max_new_tokens,
                num_beams=4,
                do_sample=False,
            )
        value = tokenizer.batch_decode(tokens, skip_special_tokens=True)[0].strip()
        if not value:
            raise ValueError("Translation model returned empty text")
        return value, f"{entry['repository']}@{entry['revision']}"

    def translate(self, text: str, source: str, target: str) -> TranslationOutput:
        if source not in SUPPORTED_LANGUAGES or target not in SUPPORTED_LANGUAGES:
            raise ValueError("Only tr/el/en translation is supported")
        if source == target:
            raise ValueError("Source and target must differ")
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Translation input must be 1..8000 characters")
        if source == "en" or target == "en":
            value, revision = self._direct(text, source, target)
            return TranslationOutput(value, (source, target), (revision,), False)
        pivot, first_revision = self._direct(text, source, "en")
        value, second_revision = self._direct(pivot, "en", target)
        return TranslationOutput(
            value,
            (source, "en", target),
            (first_revision, second_revision),
            True,
        )
