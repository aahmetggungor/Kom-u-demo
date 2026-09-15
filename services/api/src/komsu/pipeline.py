import re
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ai import Analyzer, BaselineAnalyzer, TranslationOutput, Translator
from .geolocation import Candidate, Geocoder, GeocoderUnavailable, location_annotation

NEGATIONS = {
    "tr": re.compile(r"\b(değil|yok|gerekmi(?:yor|z)|gönderme(?:yin)?)\b", re.I),
    "el": re.compile(r"\b(δεν|όχι|μην|χωρίς)\b", re.I),
    "en": re.compile(r"\b(not|don't|doesn't|do not|without|unnecessary)\b|\bno\b(?!\s*\d)", re.I),
}


def translation_guardrails(source: str, source_language: str, target: str, target_language: str):
    warnings = []
    numbers = re.compile(r"\d+(?:[.,]\d+)?")
    source_numbers, target_numbers = (
        Counter(numbers.findall(source)),
        Counter(numbers.findall(target)),
    )
    if source_numbers - target_numbers:
        warnings.append("NUMERALS_CHANGED_OR_DROPPED")
    source_negation = bool(NEGATIONS[source_language].search(source))
    if source_negation and not NEGATIONS[target_language].search(target):
        warnings.append("NEGATION_NOT_DETECTED_IN_OUTPUT")
    return warnings


class ValidatedAnalysis(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    pipeline_version: str = Field(max_length=120)
    original_language: Literal["tr", "el", "en", "und"]
    needs: list[Literal["rescue", "medical", "shelter", "water", "food"]] = Field(max_length=5)
    urgency_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    incident_type: Literal["earthquake", "flood", "wildfire", "unknown"]
    ai_confidence: float = Field(ge=0, le=1)
    human_review_required: Literal[True]
    stages: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    location_candidates: list[Candidate] = Field(default_factory=list, max_length=5)


class Pipeline:
    def __init__(
        self,
        tenant_id: str,
        analyzer: Analyzer | None = None,
        geocoder: Geocoder | None = None,
        translator: Translator | None = None,
    ):
        self.tenant_id = tenant_id
        self.analyzer = analyzer or BaselineAnalyzer()
        self.geocoder = geocoder
        self.translator = translator

    def analyze(self, text: str, language: str, address: str | None) -> dict:
        result = ValidatedAnalysis.model_validate(
            self.analyzer.analyze(text, language, address)
        ).model_dump()
        if self.geocoder and address:
            try:
                result.update(
                    location_annotation(
                        self.geocoder.candidates(
                            self.tenant_id, address, result["original_language"]
                        )
                    )
                )
                result["stages"]["geocoding"] = "candidates_require_review"
            except GeocoderUnavailable:
                result["warnings"].append("GEOCODER_UNAVAILABLE")
                result["stages"]["geocoding"] = "failed_manual_review"
        if self.translator and result["original_language"] != "und":
            result["warnings"] = [
                warning for warning in result["warnings"] if warning != "TRANSLATION_UNAVAILABLE"
            ]
            translations = {}
            provenance = {}
            for target in ("tr", "el", "en"):
                if target == result["original_language"]:
                    continue
                try:
                    translated = self.translator.translate(
                        text, result["original_language"], target
                    )
                    metadata = None
                    adapter_warnings: tuple[str, ...] = ()
                    if isinstance(translated, TranslationOutput):
                        adapter_warnings = translated.warnings
                        metadata = {
                            "route": list(translated.route),
                            "model_revisions": list(translated.model_revisions),
                            "pivoted": translated.pivoted,
                            "protection_version": translated.protection_version,
                            "protected_categories": list(translated.protected_categories),
                        }
                        for warning in adapter_warnings:
                            result["warnings"].append(f"TRANSLATION_{warning}_{target}")
                        if translated.pivoted:
                            result["warnings"].append(f"TRANSLATION_EN_PIVOT_{target}")
                        translated = translated.text
                    if (
                        not isinstance(translated, str)
                        or not translated.strip()
                        or len(translated) > 32000
                    ):
                        raise ValueError("invalid translation")
                    translations[target] = translated
                    guardrail_warnings = translation_guardrails(
                        text, result["original_language"], translated, target
                    )
                    for warning in guardrail_warnings:
                        result["warnings"].append(f"TRANSLATION_{warning}_{target}")
                    if metadata is not None:
                        metadata["warnings"] = list(
                            dict.fromkeys((*adapter_warnings, *guardrail_warnings))
                        )
                        provenance[target] = metadata
                except Exception:
                    result["warnings"].append(f"TRANSLATION_UNAVAILABLE_{target}")
            result["translated_text"] = translations
            result["translation_provenance"] = provenance
            result["translation_status"] = (
                "COMPLETE"
                if len(translations) == 2
                else "PARTIAL"
                if translations
                else "UNAVAILABLE"
            )
            if not translations:
                result["warnings"].append("TRANSLATION_UNAVAILABLE")
            result["stages"]["translation"] = result["translation_status"].lower()
        return result
