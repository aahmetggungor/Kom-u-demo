"""Conservative runnable baseline. Heuristics are not calibrated probabilities."""

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def folded(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", normalize(text)) if not unicodedata.combining(c)
    ).replace("ı", "i")


NEEDS = {
    "rescue": ["enkaz", "mahsur", "trapped", "rubble", "εγκλωβ", "ερειπ"],
    "medical": [
        "yarali",
        "ambulans",
        "kanama",
        "injured",
        "bleeding",
        "medical",
        "τραυμα",
        "ασθενοφορ",
    ],
    "shelter": ["barinak", "cadir", "shelter", "tent", "καταφυγ", "σκηνη"],
    "water": ["su", "suyu", "suya", "susuz", "water", "νερο"],
    "food": ["gida", "yemek", "food", "τροφι", "φαγη"],
}
TAXONOMY = {
    "earthquake": ["deprem", "earthquake", "σεισμ"],
    "flood": ["sel", "flood", "πλημμυρ"],
    "wildfire": ["yangin", "wildfire", "fire", "πυρκαγ"],
}


def matches(text: str, term: str) -> bool:
    # Boundary prevents 'su' in unrelated words; longer terms allow morphology suffixes.
    return bool(
        re.search(r"(?<!\w)" + re.escape(term) + (r"(?!\w)" if len(term) <= 3 else r"\w*"), text)
    )


class Analyzer(Protocol):
    def analyze(self, text: str, language: str, address: str | None) -> dict: ...


@dataclass(frozen=True)
class TranslationOutput:
    text: str
    route: tuple[str, ...]
    model_revisions: tuple[str, ...]
    pivoted: bool


class Translator(Protocol):
    def translate(self, text: str, source: str, target: str) -> str | TranslationOutput: ...


@dataclass(frozen=True)
class TranscriptionOutput:
    text: str
    language: str
    model_revision: str
    duration_seconds: float
    warnings: tuple[str, ...]


class Transcriber(Protocol):
    def transcribe(
        self, approved_local_audio: str, language_hint: str | None = None
    ) -> TranscriptionOutput: ...


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...


class LocalBgeM3:
    """Optional actual model adapter; loads approved local weights, never auto-downloads."""

    def __init__(self, model_path: str, max_tokens: int = 512):
        import hashlib
        import json
        from pathlib import Path

        path = Path(model_path).resolve()
        metadata = json.loads((path / "PROVENANCE.json").read_text(encoding="utf-8"))
        weights = (path / "pytorch_model.bin").resolve()
        if path not in weights.parents or not weights.is_file():
            raise ValueError("Embedding weights escape or are absent from approved model root")
        with weights.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != metadata["weights_sha256"]:
            raise ValueError("Embedding weights fail recorded SHA-256 verification")
        from sentence_transformers import SentenceTransformer

        if not 32 <= max_tokens <= 8192:
            raise ValueError("Unsupported embedding input limit")
        self.model = SentenceTransformer(
            str(path),
            local_files_only=True,
            trust_remote_code=False,
            model_kwargs={"weights_only": True},
        )
        self.model.max_seq_length = max_tokens

    def encode(self, texts: list[str]) -> list[list[float]]:
        result = self.model.encode(
            texts, normalize_embeddings=True, batch_size=4, show_progress_bar=False
        )
        if result.shape[1] != 1024:
            raise ValueError("Expected bge-m3 1024-dimensional embeddings")
        return result.tolist()


class BaselineAnalyzer:
    def analyze(self, text: str, language: str = "und", address: str | None = None) -> dict:
        value = folded(text)
        if language == "und":
            if re.search(r"[\u0370-\u03ff]", text):
                language = "el"
            elif any(
                matches(value, x)
                for x in ["deprem", "enkaz", "yardim", "mahsur", "yarali", "su", "cadir"]
            ):
                language = "tr"
            elif any(
                matches(value, x)
                for x in ["help", "trapped", "water", "earthquake", "injured", "shelter"]
            ):
                language = "en"
        needs = [key for key, terms in NEEDS.items() if any(matches(value, term) for term in terms)]
        types = [
            key for key, terms in TAXONOMY.items() if any(matches(value, term) for term in terms)
        ]
        warnings = ["UNCALIBRATED_BASELINE", "HUMAN_REVIEW_REQUIRED", "TRANSLATION_UNAVAILABLE"]
        if re.search(r"\b(no|not|yok|degil|δεν|οχι)\b", value):
            warnings.append("NEGATION_REQUIRES_REVIEW")
        urgency = (
            "CRITICAL"
            if "rescue" in needs
            else "HIGH"
            if "medical" in needs
            else "MEDIUM"
            if needs
            else "UNKNOWN"
        )
        count = re.search(r"\b(\d{1,3})\s*(kisi|people|persons|ατομα|ανθρωπ)", value)
        return {
            "pipeline_version": "rules-0.1",
            "original_language": language,
            "normalized_text": normalize(text),
            "translated_text": {},
            "translation_status": "UNAVAILABLE",
            "incident_type": types[0] if len(types) == 1 else "unknown",
            "needs": needs,
            "urgency_level": urgency,
            "urgency_score": {"CRITICAL": 0.9, "HIGH": 0.7, "MEDIUM": 0.5, "UNKNOWN": 0.0}[urgency],
            "people_count": int(count.group(1)) if count else None,
            "possible_trapped_people": "rescue" in needs,
            "medical_need": "medical" in needs,
            "address_raw": address,
            "location": {"lat": None, "lon": None, "confidence": 0.0},
            "location_candidates": [],
            "location_status": "AMBIGUOUS_LOCATION",
            "ai_confidence": 0.35 if needs else 0.0,
            "duplicate_cluster_id": None,
            "human_review_required": True,
            "warnings": warnings,
            "stages": {
                "language": "heuristic",
                "transcription": "not_applicable_text",
                "normalization": "completed",
                "classification": "heuristic",
                "ner": "not_configured",
                "geocoding": "not_configured",
                "translation": "not_configured",
                "duplicate": "proposal_only",
            },
        }


GUARDED_NEED_PATTERNS = {
    "tr": {
        "rescue": (r"\benkaz\w*", r"\bmahsur\w*", r"\bsikisti\w*", r"\bcikaram\w*", r"catida kald"),
        "medical": (
            r"\byarali\w*",
            r"\bambulans\w*",
            r"\bkanama\w*",
            r"saglik ekibi",
            r"nefes alam",
        ),
        "shelter": (
            r"\bbarinak\w*",
            r"\bcadir\w*",
            r"kalacak yer",
            r"geceyi (?:disarida|acikta)",
            r"ev\w*.*(?:yikildi|oturulamaz)",
        ),
        "water": (
            r"\bsu(?:yu|ya|suz)?\b",
            r"icme suyu",
            r"icecek.*(?:kalmadi|bulam)",
            r"musluk\w* kuru",
        ),
        "food": (r"\bgida\w*", r"\byemek\w*", r"\byiyece\w*", r"erzak.*tuken", r"cocuklar ac\b"),
    },
    "en": {
        "rescue": (
            r"\btrapped\b",
            r"\brubble\b",
            r"\bpinned\b",
            r"cannot get out",
            r"stranded.*roof",
        ),
        "medical": (
            r"\binjured\b",
            r"\bbleeding\b",
            r"\bmedical\b",
            r"health team",
            r"cannot breathe",
            r"losing blood",
        ),
        "shelter": (
            r"\bshelter\b",
            r"\btent\b",
            r"place to sleep",
            r"sleep outdoors",
            r"somewhere to stay",
            r"home.*(?:collapsed|uninhabitable)",
        ),
        "water": (
            r"\bdrinking water\b",
            r"\bbring water\b",
            r"\bneed(?:ed)? water\b",
            r"\bwater (?:is )?(?:needed|required)\b",
            r"nothing.*drink",
            r"taps? (?:are )?dry",
        ),
        "food": (r"\bfood\b", r"something to eat", r"supplies.*gone", r"\bhungry\b"),
    },
    "el": {
        "rescue": (r"\bεγκλωβ\w*", r"\bερειπ\w*", r"\bπαγιδευ\w*", r"αποκλειστ\w*.*στεγη"),
        "medical": (r"\bτραυμα\w*", r"\bασθενοφορ\w*", r"\bιατρικ\w*", r"χανουν αιμα", r"αναπνευσ"),
        "shelter": (
            r"\bκαταφυγ\w*",
            r"\bσκην\w*",
            r"μεροσ να (?:κοιμηθ|μειν)",
            r"κοιμηθουν εξω",
            r"σπιτι.*δεν κατοικ",
        ),
        "water": (
            r"\bχρειαζ\w* νερο\b",
            r"\bφερτε\w*.*νερο\b",
            r"\bποσιμο\w*",
            r"βρυσεσ.*στεγν",
            r"τιποτα να πιουμε",
        ),
        "food": (r"\bτροφι\w*", r"\bφαγη\w*", r"να φαμε", r"\bπειν\w*", r"προμηθειεσ.*τελειω"),
    },
}

ABSENCE_PATTERNS = {
    "tr": {
        "rescue": (r"(?:kimse )?(?:mahsur|enkaz\w*) (?:degil|yok)",),
        "medical": (r"yarali (?:degil|yok)", r"yaralanan olmadi"),
    },
    "en": {
        "rescue": (r"(?:no one|nobody|no people|not) (?:is |are )?trapped",),
        "medical": (r"(?:no one|nobody) (?:is )?injured", r"no (?:injuries|casualties)"),
    },
    "el": {
        "rescue": (r"κανεισ δεν (?:ειναι )?εγκλωβ", r"δεν υπαρχουν.{0,80}εγκλωβ"),
        "medical": (r"δεν υπαρχουν τραυμα",),
    },
}

ENDED_EXERCISE = {
    "tr": r"\b(?:tatbikat|senaryo)\b.*\b(?:bitti|sona erdi|tamamlandi)\b",
    "en": r"\b(?:drill|exercise|scenario)\b.*\b(?:ended|finished|complete)\w*\b",
    "el": r"\b(?:ασκηση|σεναριο)\b.*\b(?:τελειω|ολοκληρω)\w*",
}
UNCERTAINTY = {
    "tr": r"\b(?:olabilir|bilmiyoruz|sanirim|belki)\b",
    "en": r"\b(?:may|might|unknown|do not know|unsure)\b",
    "el": r"\b(?:ισωσ|δεν γνωριζ|αγνωστ)\w*",
}
NUMBER_MARKERS = {
    "tr": r"\b(?:bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz|on)\b|\d",
    "en": r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b|\d",
    "el": r"\b(?:ενα|μια|δυο|τρεισ|τεσσερι|πεντε|εξι|επτα|οκτω|εννεα|δεκα)\w*\b|\d",
}


class GuardedRulesAnalyzer:
    """Evaluation candidate with explicit negation/indirect-need guardrails."""

    def analyze(self, text: str, language: str = "und", address: str | None = None) -> dict:
        baseline = BaselineAnalyzer().analyze(text, language, address)
        language = baseline["original_language"]
        if language not in GUARDED_NEED_PATTERNS:
            baseline["pipeline_version"] = "rules-0.2-candidate"
            baseline["warnings"].append("CLASSIFICATION_LANGUAGE_UNAVAILABLE")
            return baseline
        value = folded(text)
        exercise_ended = bool(re.search(ENDED_EXERCISE[language], value))
        needs = []
        if not exercise_ended:
            for need, patterns in GUARDED_NEED_PATTERNS[language].items():
                present = any(re.search(pattern, value) for pattern in patterns)
                absent = any(
                    re.search(pattern, value)
                    for pattern in ABSENCE_PATTERNS.get(language, {}).get(need, ())
                )
                if present and not absent:
                    needs.append(need)
        urgency = (
            "CRITICAL"
            if "rescue" in needs
            else "HIGH"
            if "medical" in needs
            else "MEDIUM"
            if needs
            else "UNKNOWN"
        )
        types = [
            key for key, terms in TAXONOMY.items() if any(matches(value, term) for term in terms)
        ]
        warnings = [
            "UNCALIBRATED_CANDIDATE",
            "HUMAN_REVIEW_REQUIRED",
            "TRANSLATION_UNAVAILABLE",
            "NO_AUTOMATIC_DISPATCH",
        ]
        if exercise_ended:
            warnings.append("ENDED_EXERCISE_REQUIRES_REVIEW")
        if any(
            re.search(pattern, value)
            for patterns in ABSENCE_PATTERNS.get(language, {}).values()
            for pattern in patterns
        ):
            warnings.append("NEGATION_SCOPE_APPLIED_REVIEW")
        if re.search(NUMBER_MARKERS[language], value):
            warnings.append("NUMERALS_REQUIRE_REVIEW")
        if re.search(UNCERTAINTY[language], value):
            warnings.append("AMBIGUOUS_STATEMENT_REQUIRES_REVIEW")
        baseline.update(
            {
                "pipeline_version": "rules-0.2-candidate",
                "incident_type": "unknown"
                if exercise_ended
                else types[0]
                if len(types) == 1
                else "unknown",
                "needs": needs,
                "urgency_level": urgency,
                "urgency_score": {"CRITICAL": 0.9, "HIGH": 0.7, "MEDIUM": 0.5, "UNKNOWN": 0.0}[
                    urgency
                ],
                "possible_trapped_people": "rescue" in needs,
                "medical_need": "medical" in needs,
                "ai_confidence": 0.35 if needs else 0.0,
                "human_review_required": True,
                "warnings": warnings,
                "classification_provenance": {
                    "candidate": "guarded-multilingual-rules",
                    "revision": "rules-0.2-candidate",
                    "calibrated": False,
                    "automatic_action": False,
                },
            }
        )
        return baseline


@dataclass(frozen=True)
class DuplicateEvidence:
    score: float
    semantic_similarity: float
    location_similarity: float
    time_similarity: float
    entity_similarity: float
    propose_merge: bool
    reason: str


def duplicate_evidence(
    semantic: float,
    distance_m: float | None,
    time_delta_seconds: float,
    same_building: bool,
    conflicting_entities: bool,
) -> DuplicateEvidence:
    if not math.isfinite(semantic) or not -1 <= semantic <= 1:
        raise ValueError("invalid cosine score")
    if not math.isfinite(time_delta_seconds) or (
        distance_m is not None and (not math.isfinite(distance_m) or distance_m < 0)
    ):
        raise ValueError("invalid metadata")
    location = math.exp(-distance_m / 50) if distance_m is not None else 0.0
    time_score = math.exp(-abs(time_delta_seconds) / 3600)
    entity = float(same_building and not conflicting_entities)
    score = 0.45 * max(0, semantic) + 0.25 * location + 0.15 * time_score + 0.15 * entity
    safe = (
        semantic >= 0.92
        and distance_m is not None
        and distance_m <= 30
        and abs(time_delta_seconds) <= 3600
        and same_building
        and not conflicting_entities
        and score >= 0.88
    )
    return DuplicateEvidence(
        score,
        semantic,
        location,
        time_score,
        entity,
        safe,
        "HUMAN_CONFIRMATION_REQUIRED" if safe else "INSUFFICIENT_OR_CONFLICTING_EVIDENCE",
    )
