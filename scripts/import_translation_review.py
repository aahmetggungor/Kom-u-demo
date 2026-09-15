"""Validate completed offline translation reviews and emit aggregate evidence only."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from export_translation_review import CORE_FIELDS, REVIEW_FIELDS, digest

FOCUSED_FIELDS = (
    "meaning_preserved",
    "critical_error",
    "numbers_correct",
    "names_addresses_correct",
    "negation_correct",
    "terminology_correct",
)


def import_reviews(input_path: Path, output_path: Path) -> dict:
    with input_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Review CSV has no cases")
    directions: dict[str, list[dict]] = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        missing = set((*CORE_FIELDS, "case_sha256", *REVIEW_FIELDS)) - set(row)
        if missing:
            raise ValueError(f"Line {line}: missing columns {sorted(missing)}")
        if digest(row) != row["case_sha256"]:
            raise ValueError(f"Line {line}: source or machine output changed after export")
        try:
            adequacy = int(row["adequacy_1_5"])
        except ValueError as exc:
            raise ValueError(f"Line {line}: adequacy_1_5 must be 1..5") from exc
        if adequacy not in range(1, 6):
            raise ValueError(f"Line {line}: adequacy_1_5 must be 1..5")
        normalized = {field: row[field].strip().casefold() for field in FOCUSED_FIELDS}
        if any(value not in {"yes", "no", "na"} for value in normalized.values()):
            raise ValueError(f"Line {line}: focused checks must be yes, no or na")
        if row["reviewer_native_language"].strip().casefold() not in {"tr", "el", "en"}:
            raise ValueError(f"Line {line}: reviewer_native_language must be tr, el or en")
        directions[f"{row['source_language']}→{row['target_language']}"].append(
            {"adequacy": adequacy, **normalized}
        )

    def summary(values: list[dict]) -> dict:
        count = len(values)
        return {
            "reviews": count,
            "mean_adequacy": round(sum(value["adequacy"] for value in values) / count, 3),
            "adequacy_at_least_4": sum(value["adequacy"] >= 4 for value in values),
            "critical_errors": sum(value["critical_error"] == "yes" for value in values),
            "critical_error_rate": round(
                sum(value["critical_error"] == "yes" for value in values) / count, 3
            ),
            "focused_failures": {
                field: sum(value[field] == "no" for value in values)
                for field in FOCUSED_FIELDS
                if field != "critical_error"
            },
        }

    all_values = [value for values in directions.values() for value in values]
    payload = {
        "kind": "native-speaker-review-aggregate-no-free-text",
        "source_file": input_path.name,
        "overall": summary(all_values),
        "by_direction": {direction: summary(values) for direction, values in directions.items()},
        "promotion_decision": "REQUIRES_PROJECT_OWNER_REVIEW",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evaluation/translation-human-review-summary.json"),
    )
    args = parser.parse_args()
    payload = import_reviews(args.input, args.output)
    print(json.dumps(payload["overall"], ensure_ascii=False))


if __name__ == "__main__":
    main()
