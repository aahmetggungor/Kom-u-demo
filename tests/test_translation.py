import json

import pytest
from komsu.translation import LocalMarianTranslator


def manifest(tmp_path):
    routes = {
        route: {
            "directory": route,
            "repository": f"example/{route}",
            "revision": "abc123",
            "weights_file": "model.safetensors",
            "weights_sha256": "unused-by-mocked-direct-call",
        }
        for route in ("tr-en", "en-tr", "el-en", "en-el")
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"routes": routes}))
    return routes


def test_direct_and_pivot_routes_keep_revision_provenance(tmp_path, monkeypatch):
    manifest(tmp_path)
    translator = LocalMarianTranslator(tmp_path)
    calls = []

    def direct(text, source, target):
        calls.append((text, source, target))
        return f"{target}:{text}", f"example/{source}-{target}@abc123"

    monkeypatch.setattr(translator, "_direct", direct)
    direct_result = translator.translate("help", "en", "tr")
    assert direct_result.route == ("en", "tr")
    assert direct_result.pivoted is False
    pivot = translator.translate("yardım", "tr", "el")
    assert pivot.text == "el:en:yardım"
    assert pivot.route == ("tr", "en", "el")
    assert pivot.pivoted is True
    assert calls[-2:] == [("yardım", "tr", "en"), ("en:yardım", "en", "el")]


@pytest.mark.parametrize(
    ("text", "source", "target"),
    [("", "tr", "en"), ("x", "und", "en"), ("x", "tr", "tr"), ("x" * 8001, "tr", "en")],
)
def test_rejects_unsupported_or_unbounded_input(tmp_path, text, source, target):
    manifest(tmp_path)
    translator = LocalMarianTranslator(tmp_path)
    with pytest.raises(ValueError):
        translator.translate(text, source, target)


def test_manifest_must_contain_only_approved_routes(tmp_path):
    routes = manifest(tmp_path)
    routes["tr-el"] = routes["tr-en"]
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"routes": routes}))
    with pytest.raises(ValueError):
        LocalMarianTranslator(tmp_path)


def test_weight_digest_is_checked_before_model_loader_import(tmp_path):
    routes = manifest(tmp_path)
    model_dir = tmp_path / "tr-en"
    model_dir.mkdir()
    (model_dir / "model.safetensors").write_bytes(b"tampered")
    routes["tr-en"]["weights_sha256"] = "0" * 64
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"routes": routes}))
    translator = LocalMarianTranslator(tmp_path)
    with pytest.raises(ValueError, match="SHA-256"):
        translator._load("tr-en")
