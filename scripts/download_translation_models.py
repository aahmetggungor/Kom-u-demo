"""Provision four pinned OPUS-MT routes locally and record license/checksum provenance."""

import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path("models/opus-mt")
ROUTES = {
    "tr-en": {
        "repository": "Helsinki-NLP/opus-mt-tr-en",
        "revision": "19c65427cc2af5f191337d4899e0348c4af25902",
        "weights_sha256": "e2b820f31c9348b0ae33d77ac23bd1686fa60a8afa0b9511bc7d9a35c125b534",
        "license": "Apache-2.0",
        "weights_file": "pytorch_model.bin",
    },
    "en-tr": {
        "repository": "Helsinki-NLP/opus-mt-en-trk",
        "revision": "f9d8f6cd9d95d2f8ce34943c1f6cfe610d3bbf92",
        "weights_sha256": "8382c39effafc5e3b9f5b0fcdcd10a7efbc551ef57398b6bf175d2e986ecec86",
        "license": "Apache-2.0",
        "weights_file": "pytorch_model.bin",
        "target_prefix": ">>tur<< ",
    },
    "el-en": {
        "repository": "Helsinki-NLP/opus-mt_tiny_ell-eng",
        "revision": "beff0d92479a72deff22f722ab28efa81d2ac8a9",
        "weights_sha256": "15fe617eac2acb5d924f809bbcdf627dd31f75850928c1ae260a5934876d9837",
        "license": "Apache-2.0",
        "weights_file": "model.safetensors",
        "directory": "el-en-tiny",
    },
    "en-el": {
        "repository": "Helsinki-NLP/opus-mt-en-el",
        "revision": "1653673990e6f1e3baf0a903f38e231730704444",
        "weights_sha256": "11dc5a1b560806b1096c96cbf722ef5198ebb28b7b4115ea579261c54de40207",
        "license": "Apache-2.0",
        "weights_file": "pytorch_model.bin",
    },
}
FILES = [
    "README.md",
    "config.json",
    "generation_config.json",
    "added_tokens.json",
    "source.spm",
    "special_tokens_map.json",
    "target.spm",
    "tokenizer_config.json",
    "vocab.json",
    "pytorch_model.bin",
    "model.safetensors",
]


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {"format": 1, "routes": {}}
    for route, metadata in ROUTES.items():
        destination = ROOT / metadata.get("directory", route)
        snapshot_download(
            repo_id=metadata["repository"],
            revision=metadata["revision"],
            local_dir=destination,
            token=False,
            allow_patterns=FILES,
        )
        weights = destination / metadata["weights_file"]
        with weights.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != metadata["weights_sha256"]:
            raise RuntimeError(f"{route} weights differ from recorded revision digest")
        entry = {
            **metadata,
            "directory": metadata.get("directory", route),
            "weights_bytes": weights.stat().st_size,
            "loading": "local_files_only; trust_remote_code=False; weights_only=True",
        }
        manifest["routes"][route] = entry
        (destination / "PROVENANCE.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (ROOT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("docs/evaluation/translation-provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
