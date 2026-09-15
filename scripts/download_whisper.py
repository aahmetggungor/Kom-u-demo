"""Provision a pinned official Whisper model locally and verify safetensors."""

import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

REPOSITORY = "openai/whisper-tiny"
REVISION = "169d4a4341b33bc18d8881c4b69c2e104e1cc0af"
WEIGHTS = "model.safetensors"
SHA256 = "7ebd0e69e78190ffe1438491fa05cc1f5c1aa3a4c4db3bc1723adbb551ea2395"
DESTINATION = Path("models/whisper-tiny")


def main() -> None:
    snapshot_download(
        repo_id=REPOSITORY,
        revision=REVISION,
        local_dir=DESTINATION,
        token=False,
        allow_patterns=[
            "README.md",
            "added_tokens.json",
            "config.json",
            "generation_config.json",
            "merges.txt",
            WEIGHTS,
            "normalizer.json",
            "preprocessor_config.json",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
        ],
    )
    weights = DESTINATION / WEIGHTS
    with weights.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    if checksum != SHA256:
        raise RuntimeError("Whisper weights differ from recorded revision digest")
    metadata = {
        "repository": REPOSITORY,
        "revision": REVISION,
        "license": "Apache-2.0",
        "weights_file": WEIGHTS,
        "weights_sha256": checksum,
        "weights_bytes": weights.stat().st_size,
        "loading": "local_files_only; trust_remote_code=False; weights_only=True",
    }
    (DESTINATION / "PROVENANCE.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    Path("docs/evaluation/whisper-provenance.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
