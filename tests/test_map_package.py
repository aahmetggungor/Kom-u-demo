import hashlib
import json
from pathlib import Path

import pytest
from komsu.map_package import MapPackageUnavailable, load_map_package


def write_package(tmp_path, style, **updates):
    body = json.dumps(style, ensure_ascii=False, separators=(",", ":")).encode()
    (tmp_path / "style.json").write_bytes(body)
    manifest = {
        "enabled": True,
        "package_version": "test-1",
        "updated_at": "2026-09-15T00:00:00+00:00",
        "stale_after_days": 30,
        "license_name": "Synthetic fixture",
        "attribution": "Synthetic only",
        "style_file": "style.json",
        "style_sha256": hashlib.sha256(body).hexdigest(),
        "allowed_origins": [],
    }
    manifest.update(updates)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_verified_synthetic_map_package_loads():
    root = Path(__file__).parents[1]
    result = load_map_package(root / "data/map-package.synthetic/manifest.json")
    assert result["enabled"] and result["style"]["version"] == 8
    assert result["package_version"] == "synthetic-contract-1"


def test_tampered_or_public_tile_style_fails_closed(tmp_path):
    style = {"version": 8, "sources": {}, "layers": []}
    manifest = write_package(tmp_path, style)
    (tmp_path / "style.json").write_text("{}")
    with pytest.raises(MapPackageUnavailable):
        load_map_package(manifest)

    public = {
        "version": 8,
        "sources": {
            "osm": {"type": "raster", "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"]}
        },
        "layers": [],
    }
    with pytest.raises(MapPackageUnavailable):
        load_map_package(write_package(tmp_path, public))

    with pytest.raises(MapPackageUnavailable):
        load_map_package(
            write_package(tmp_path, style, allowed_origins={"https://tiles.example": True})
        )


def test_disabled_package_exposes_metadata_without_style(tmp_path):
    manifest = write_package(tmp_path, {"version": 8, "sources": {}, "layers": []}, enabled=False)
    result = load_map_package(manifest)
    assert result["enabled"] is False and result["style"] is None
