import pytest
from komsu.ai import TranslationOutput
from komsu.geolocation import GeocoderUnavailable
from komsu.pipeline import Pipeline, ValidatedAnalysis, translation_guardrails


def test_geocoder_outage_isolated_from_classifier():
    class Broken:
        def candidates(self, *args):
            raise GeocoderUnavailable("provider error")

    result = Pipeline("tenant", geocoder=Broken()).analyze(
        "People trapped", "en", "Synthetic address"
    )
    assert result["urgency_level"] == "CRITICAL"
    assert "GEOCODER_UNAVAILABLE" in result["warnings"]
    assert result["location"]["lat"] is None


def test_invalid_model_result_cannot_disable_human_review():
    result = Pipeline("tenant").analyze("help", "en", None)
    result["human_review_required"] = False
    with pytest.raises(ValueError):
        ValidatedAnalysis.model_validate(result)
    result["human_review_required"] = True
    result["ai_confidence"] = float("nan")
    with pytest.raises(ValueError):
        ValidatedAnalysis.model_validate(result)


def test_minimal_valid_analyzer_metadata_defaults_and_bad_candidates():
    result = Pipeline("tenant").analyze("help", "en", None)
    result.pop("warnings")
    result.pop("stages")
    validated = ValidatedAnalysis.model_validate(result)
    assert validated.warnings == []
    assert validated.stages == {}
    result["location_candidates"] = [{"lat": "not a coordinate"}]
    with pytest.raises(ValueError):
        ValidatedAnalysis.model_validate(result)


def test_translation_provenance_and_pivot_warning_are_retained():
    class Translator:
        def translate(self, text, source, target):
            return TranslationOutput(
                f"{target}:{text}",
                (source, "en", target) if target == "el" else (source, target),
                ("model-a@revision", "model-b@revision")
                if target == "el"
                else ("model-a@revision",),
                target == "el",
                ("PROTECTED_NUMBER_RECOVERED",),
                "placeholder-terminology-1",
                ("number",),
            )

    result = Pipeline("tenant", translator=Translator()).analyze("yardım", "tr", None)
    assert result["translation_status"] == "COMPLETE"
    assert result["translated_text"] == {"el": "el:yardım", "en": "en:yardım"}
    assert result["translation_provenance"]["el"]["route"] == ["tr", "en", "el"]
    assert result["translation_provenance"]["el"]["pivoted"] is True
    assert (
        result["translation_provenance"]["el"]["protection_version"] == "placeholder-terminology-1"
    )
    assert "TRANSLATION_PROTECTED_NUMBER_RECOVERED_el" in result["warnings"]
    assert "TRANSLATION_EN_PIVOT_el" in result["warnings"]
    assert result["stages"]["translation"] == "complete"
    assert "TRANSLATION_UNAVAILABLE" not in result["warnings"]


def test_translation_guardrails_detect_dropped_number_and_negation():
    warnings = translation_guardrails(
        "No 8: 3 kişi var, su gerekmiyor.", "tr", "There are three people.", "en"
    )
    assert warnings == ["NUMERALS_CHANGED_OR_DROPPED", "NEGATION_NOT_DETECTED_IN_OUTPUT"]
    assert translation_guardrails("3 people", "en", "3 kişi", "tr") == []
    assert translation_guardrails("No 8, 3 people", "en", "Αρ. 8, 3 άτομα", "el") == []
