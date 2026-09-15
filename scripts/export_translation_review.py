"""Create a PII-free, offline bilingual review package from synthetic diagnostics."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

REVIEW_FIELDS = (
    "adequacy_1_5",
    "meaning_preserved",
    "critical_error",
    "numbers_correct",
    "names_addresses_correct",
    "negation_correct",
    "terminology_correct",
    "reviewer_native_language",
    "review_notes",
)
CORE_FIELDS = (
    "case_id",
    "source_language",
    "target_language",
    "source_text",
    "machine_translation",
    "route",
    "protection_warnings",
)


def digest(row: dict) -> str:
    value = json.dumps(
        {key: row[key] for key in CORE_FIELDS},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def export_package(diagnostic_path: Path, output_dir: Path) -> tuple[Path, Path]:
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    rows = []
    for result in diagnostic["results"]:
        row = {
            "case_id": result["id"],
            "source_language": result["source"],
            "target_language": result["target"],
            "source_text": result["text"],
            "machine_translation": result["candidate_output"],
            "route": "→".join(result["route"]),
            "protection_warnings": "|".join(result["protection_warnings"]),
        }
        row["case_sha256"] = digest(row)
        row.update({field: "" for field in REVIEW_FIELDS})
        rows.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "translation-review.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=(*CORE_FIELDS, "case_sha256", *REVIEW_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    json_path = output_dir / "translation-review.json"
    payload = {
        "kind": "synthetic-pii-free-native-speaker-review-template",
        "instructions": [
            "Review both source and machine translation offline; do not infer from the English pivot alone.",
            "Use only the synthetic text supplied here and do not add names, phone numbers or real incident details.",
            "Score adequacy from 1 (unsafe/wrong) to 5 (fully adequate).",
            "Set critical_error=yes for omitted, invented or reversed facts that could change rescue action.",
            "Use yes, no or na for the five focused checks. Leave reviewer identity out of this file.",
        ],
        "allowed_languages": ["tr", "el", "en"],
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--diagnostic", type=Path, default=Path("docs/evaluation/translation-diagnostic.json")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/evaluation/translation-review-package"),
    )
    args = parser.parse_args()
    for path in export_package(args.diagnostic, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
