"""Explicit model provisioning from the official BAAI repository; no report upload."""

import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

repo = "BAAI/bge-m3"
destination = Path("models/bge-m3")
revision = "5617a9f61b028005a4858fdac845db406aefb181"
snapshot_download(
    repo_id=repo,
    revision=revision,
    local_dir=destination,
    token=False,
    allow_patterns=[
        "config.json",
        "config_sentence_transformers.json",
        "modules.json",
        "sentence_bert_config.json",
        "sentencepiece.bpe.model",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "1_Pooling/config.json",
        "pytorch_model.bin",
        "README.md",
    ],
)
weights = destination / "pytorch_model.bin"
with weights.open("rb") as stream:
    checksum = hashlib.file_digest(stream, "sha256").hexdigest()
if checksum != "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38":
    raise RuntimeError("Model weights differ from the recorded revision digest")
metadata = {
    "repository": repo,
    "revision": revision,
    "weights_sha256": checksum,
    "weights_bytes": weights.stat().st_size,
    "license": "MIT (model card)",
    "loading": "local files only, trust_remote_code=False, PyTorch restricted weights-only loader required",
}
(destination / "PROVENANCE.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
Path("docs/evaluation/bge-provenance.json").write_text(
    json.dumps(metadata, indent=2), encoding="utf-8"
)
print(json.dumps(metadata, indent=2))
