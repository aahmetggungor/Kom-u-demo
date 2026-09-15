"""Run an authored local smoke set; results are diagnostics, not a quality benchmark."""

import json
import re
import time
from pathlib import Path

from komsu.translation import LocalMarianTranslator

CASES = [
    {
        "id": "tr-en-negation-address",
        "source": "tr",
        "target": "en",
        "text": "Alsancak 1462 Sokak No 8, enkaz altında 3 kişi var. Su gerekmiyor.",
        "protected_terms": ["Alsancak"],
        "expects_negation": True,
    },
    {
        "id": "en-tr-negation-address",
        "source": "en",
        "target": "tr",
        "text": "At 8 Seaside Street, 2 people are trapped. Do not send food.",
        "protected_terms": ["Seaside"],
        "expects_negation": True,
    },
    {
        "id": "el-en-negation-address",
        "source": "el",
        "target": "en",
        "text": "Στην οδό Σμύρνης 12 υπάρχουν 4 τραυματίες. Δεν χρειαζόμαστε νερό.",
        "protected_terms": ["Σμύρνης"],
        "expects_negation": True,
    },
    {
        "id": "en-el-negation-address",
        "source": "en",
        "target": "el",
        "text": "At Smyrna Street 12 there are 4 injured people. We do not need water.",
        "protected_terms": ["Smyrna"],
        "expects_negation": True,
    },
    {
        "id": "tr-el-pivot-count",
        "source": "tr",
        "target": "el",
        "text": "Bornova Kazımdirik Mahallesi'nde 5 yaralı var, ambulans gerekli.",
        "protected_terms": ["Bornova", "Kazımdirik"],
        "expects_negation": False,
    },
    {
        "id": "el-tr-pivot-count",
        "source": "el",
        "target": "tr",
        "text": "Στο χωριό Βρίσα υπάρχουν 6 εγκλωβισμένοι και χρειάζεται ασθενοφόρο.",
        "protected_terms": ["Βρίσα"],
        "expects_negation": False,
    },
]
NEGATION = {
    "tr": re.compile(r"\b(değil|yok|gerekmi(?:yor|z)|gönderme(?:yin)?)\b", re.I),
    "el": re.compile(r"\b(δεν|όχι|μην|χωρίς)\b", re.I),
    "en": re.compile(r"\b(no|not|don't|doesn't|do not|without|unnecessary)\b", re.I),
}


def numerals(text: str) -> list[str]:
    return re.findall(r"\d+", text)


def main() -> None:
    translator = LocalMarianTranslator("models/opus-mt", max_new_tokens=128)
    rows = []
    for case in CASES:
        started = time.perf_counter()
        result = translator.translate(case["text"], case["source"], case["target"])
        source_numbers = numerals(case["text"])
        row = {
            **case,
            "output": result.text,
            "route": list(result.route),
            "model_revisions": list(result.model_revisions),
            "pivoted": result.pivoted,
            "seconds": round(time.perf_counter() - started, 3),
            "source_numerals": source_numbers,
            "numerals_preserved": all(n in numerals(result.text) for n in source_numbers),
            "protected_terms_preserved_verbatim": all(
                term.casefold() in result.text.casefold() for term in case["protected_terms"]
            ),
            "negation_marker_present": (
                bool(NEGATION[case["target"]].search(result.text))
                if case["expects_negation"]
                else None
            ),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = {
        "kind": "authored-smoke-diagnostic-not-a-quality-benchmark",
        "human_bilingual_review": "NOT_PERFORMED",
        "cases": len(rows),
        "numerals_preserved": sum(row["numerals_preserved"] for row in rows),
        "protected_terms_preserved_verbatim": sum(
            row["protected_terms_preserved_verbatim"] for row in rows
        ),
        "negation_marker_present": sum(row["negation_marker_present"] is True for row in rows),
        "negation_cases": sum(row["expects_negation"] for row in rows),
    }
    output = {"summary": summary, "results": rows}
    Path("docs/evaluation/translation-diagnostic.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
