"""Offline Marian translation adapter for explicitly provisioned model packs."""

import gc
import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .ai import TranslationOutput

SUPPORTED_LANGUAGES = frozenset({"tr", "el", "en"})
PROTECTION_VERSION = "placeholder-terminology-1"
PLACEHOLDER = "KOMSUPROTECTED{:03d}TOKEN"

# Short, safety-relevant phrases only. This is not a general translation dictionary.
TERMINOLOGY = {
    "tr": {
        "enkaz": {"en": "rubble", "el": "ερείπια"},
        "ambulans": {"en": "ambulance", "el": "ασθενοφόρο"},
        "deprem": {"en": "earthquake", "el": "σεισμός"},
        "sel": {"en": "flood", "el": "πλημμύρα"},
        "yangın": {"en": "wildfire", "el": "πυρκαγιά"},
    },
    "en": {
        "rubble": {"tr": "enkaz", "el": "ερείπια"},
        "ambulance": {"tr": "ambulans", "el": "ασθενοφόρο"},
        "earthquake": {"tr": "deprem", "el": "σεισμός"},
        "flood": {"tr": "sel", "el": "πλημμύρα"},
        "wildfire": {"tr": "orman yangını", "el": "πυρκαγιά"},
    },
    "el": {
        "ερείπια": {"tr": "enkaz", "en": "rubble"},
        "ασθενοφόρο": {"tr": "ambulans", "en": "ambulance"},
        "σεισμός": {"tr": "deprem", "en": "earthquake"},
        "πλημμύρα": {"tr": "sel", "en": "flood"},
        "πυρκαγιά": {"tr": "orman yangını", "en": "wildfire"},
    },
}
NEGATION_TERMS = {
    "tr": (r"\bgöndermeyin\b", r"\bgerekmiyor\b", r"\bdeğil\b", r"\byok\b"),
    "en": (
        r"\bdo not\b",
        r"\bdon't\b",
        r"\bdoes not\b",
        r"\bdoesn't\b",
        r"\bnot\b",
        r"\bno\b(?!\s*\d)",
    ),
    "el": (r"\bδεν\b", r"\bμην\b", r"\bόχι\b", r"\bχωρίς\b"),
}
ADDRESS_PATTERNS = {
    "tr": (
        r"\b[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü'-]+\s+\d+\s+(?:Sokak|Cadde)(?:\s+No\s+\d+)?",
        r"\b(?:[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü'-]+\s+){1,3}Mahallesi",
    ),
    "en": (r"\b(?:At\s+)?\d+\s+[A-Z][A-Za-z'-]+\s+(?:Street|Road|Avenue)\b",),
    "el": (r"\b(?:οδό\s+[Α-ΩΆΈΉΊΌΎΏ][\wΆ-ώ'-]+\s+\d+|χωριό\s+[Α-ΩΆΈΉΊΌΎΏ][\wΆ-ώ'-]+)",),
}
ENTITY_PATTERNS = {
    "tr": (
        r"\b[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü'-]+(?=\s+\d+\s+(?:Sokak|Cadde))",
        r"\b(?:[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü'-]+\s+){1,3}(?=Mahallesi)",
        r"(?<=adı\s)[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü'-]+(?:\s+[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü'-]+)?",
    ),
    "en": (
        r"\b[A-Z][A-Za-z'-]+(?=\s+(?:Street|Road|Avenue|Village)\b)",
        r"(?<=name:\s)[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?",
    ),
    "el": (
        r"(?<=οδό\s)[Α-ΩΆΈΉΊΌΎΏ][\wΆ-ώ'-]+",
        r"(?<=χωριό\s)[Α-ΩΆΈΉΊΌΎΏ][\wΆ-ώ'-]+",
        r"(?<=όνομα:\s)[Α-ΩΆΈΉΊΌΎΏ][\wΆ-ώ'-]+(?:\s+[Α-ΩΆΈΉΊΌΎΏ][\wΆ-ώ'-]+)?",
    ),
}


@dataclass(frozen=True)
class ProtectedTranslation:
    text: str
    replacements: tuple[tuple[str, str, str], ...]
    target_language: str


def protect_translation_text(text: str, source: str, target: str) -> ProtectedTranslation:
    """Build a placeholder registry for safety-critical spans and non-sensitive metadata."""
    candidates: list[tuple[int, int, str, str]] = []
    for match in re.finditer(r"\d+(?:[.,]\d+)?", text):
        candidates.append((*match.span(), match.group(), "number"))
    for pattern in ADDRESS_PATTERNS[source]:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidates.append((*match.span(), match.group().strip(), "address"))
    for pattern in ENTITY_PATTERNS[source]:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidates.append((*match.span(), match.group().strip(), "name_or_place"))
    for source_term, targets in TERMINOLOGY[source].items():
        for match in re.finditer(rf"(?<!\w){re.escape(source_term)}(?!\w)", text, re.IGNORECASE):
            candidates.append((*match.span(), targets[target], "disaster_term"))
    for pattern in NEGATION_TERMS[source]:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(text.rfind(mark, 0, match.start()) for mark in ".!?;") + 1
            endings = [
                position for mark in ".!?;" if (position := text.find(mark, match.end())) >= 0
            ]
            end = min(endings) + 1 if endings else len(text)
            candidates.append((start, end, text[start:end].strip(), "negated_clause"))

    # Prefer the longest span at a position and never create overlapping placeholders.
    accepted: list[tuple[int, int, str, str]] = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]))):
        if any(candidate[0] < end and candidate[1] > start for start, end, _, _ in accepted):
            continue
        accepted.append(candidate)
    accepted.sort()
    pieces, replacements, cursor = [], [], 0
    for index, (start, end, replacement, category) in enumerate(accepted):
        marker = PLACEHOLDER.format(index)
        pieces.extend((text[cursor:start], marker))
        replacements.append((marker, replacement, category))
        cursor = end
    pieces.append(text[cursor:])
    return ProtectedTranslation("".join(pieces), tuple(replacements), target)


def restore_translation_text(
    translated: str, protected: ProtectedTranslation
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    warnings: list[str] = []
    categories: list[str] = []
    model_output = translated
    for marker, replacement, category in protected.replacements:
        categories.append(category)
        if marker in translated:
            translated = translated.replace(marker, replacement)
        elif category == "negated_clause" and any(
            re.search(pattern, model_output, re.IGNORECASE)
            for pattern in NEGATION_TERMS[protected.target_language]
        ):
            continue
        elif (
            re.search(rf"(?<!\d){re.escape(replacement)}(?!\d)", model_output)
            if category == "number"
            else replacement.casefold() in model_output.casefold()
        ):
            continue
        else:
            # Never silently lose a protected safety fact. The warning tells reviewers
            # that the visibly appended value was recovered outside model inference.
            translated = f"{translated.rstrip()} ⟦{replacement}⟧"
            warnings.append(f"PROTECTED_{category.upper()}_RECOVERED")
    return translated.strip(), tuple(dict.fromkeys(warnings)), tuple(dict.fromkeys(categories))


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

    def _guarded_direct(
        self, text: str, source: str, target: str
    ) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
        protected = protect_translation_text(text, source, target)
        # Marian models mutate opaque placeholders. Translate the intact sentence,
        # then enforce the protected-span registry as an explicit postcondition.
        value, revision = self._direct(text, source, target)
        value, warnings, categories = restore_translation_text(value, protected)
        return value, revision, warnings, categories

    def translate(self, text: str, source: str, target: str) -> TranslationOutput:
        if source not in SUPPORTED_LANGUAGES or target not in SUPPORTED_LANGUAGES:
            raise ValueError("Only tr/el/en translation is supported")
        if source == target:
            raise ValueError("Source and target must differ")
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Translation input must be 1..8000 characters")
        if source == "en" or target == "en":
            value, revision, warnings, categories = self._guarded_direct(text, source, target)
            return TranslationOutput(
                value,
                (source, target),
                (revision,),
                False,
                warnings,
                PROTECTION_VERSION,
                categories,
            )
        pivot, first_revision = self._direct(text, source, "en")
        value, second_revision = self._direct(pivot, "en", target)
        protected = protect_translation_text(text, source, target)
        value, warnings, categories = restore_translation_text(value, protected)
        return TranslationOutput(
            value,
            (source, "en", target),
            (first_revision, second_revision),
            True,
            warnings,
            PROTECTION_VERSION,
            categories,
        )
