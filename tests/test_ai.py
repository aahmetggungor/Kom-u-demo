import json

import pytest
from komsu.ai import BaselineAnalyzer, LocalBgeM3, duplicate_evidence, normalize


@pytest.mark.parametrize(
    "text,language,need",
    [
        ("Enkaz altında 3 kişi mahsur", "tr", "rescue"),
        ("Υπάρχουν εγκλωβισμένοι στα ερείπια", "el", "rescue"),
        ("People trapped under rubble", "en", "rescue"),
        ("Acil su gerekiyor", "tr", "water"),
        ("Χρειαζόμαστε νερό", "el", "water"),
        ("We need shelter", "en", "shelter"),
    ],
)
def test_multilingual_baseline(text, language, need):
    result = BaselineAnalyzer().analyze(text)
    assert result["original_language"] == language
    assert need in result["needs"]
    assert result["human_review_required"] and result["ai_confidence"] <= 0.35
    assert result["location"]["lat"] is None
    assert result["translation_status"] == "UNAVAILABLE"


def test_ambiguous_location_and_unknown():
    result = BaselineAnalyzer().analyze("Eski belediyenin karşısındaki bina", "tr")
    assert result["location_status"] == "AMBIGUOUS_LOCATION"
    assert result["urgency_level"] == "UNKNOWN"
    assert result["location_candidates"] == []


@pytest.mark.parametrize("text", ["İçme suyu gerekiyor", "Suya ihtiyacımız var", "Susuz kaldık"])
def test_turkish_water_suffixes(text):
    assert "water" in BaselineAnalyzer().analyze(text, "tr")["needs"]


def test_negation_warned_and_word_boundaries():
    result = BaselineAnalyzer().analyze("No people trapped here", "en")
    assert "NEGATION_REQUIRES_REVIEW" in result["warnings"]
    assert "water" not in BaselineAnalyzer().analyze("sunshine", "en")["needs"]
    assert normalize("  HELP\nNOW  ") == "help now"


def test_duplicate_safety_gates():
    assert duplicate_evidence(0.99, 1, 10, True, False).propose_merge
    for distance, delta, building, conflict in [
        (None, 0, True, False),
        (2, 0, False, False),
        (2, 0, True, True),
        (100, 0, True, False),
        (1, 86400, True, False),
    ]:
        assert not duplicate_evidence(0.99, distance, delta, building, conflict).propose_merge
    with pytest.raises(ValueError):
        duplicate_evidence(float("nan"), 0, 0, True, False)


def test_embedding_weight_digest_checked_before_model_import(tmp_path):
    (tmp_path / "pytorch_model.bin").write_bytes(b"tampered")
    (tmp_path / "PROVENANCE.json").write_text(
        json.dumps({"weights_sha256": "0" * 64}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="SHA-256"):
        LocalBgeM3(str(tmp_path))
