import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from export_translation_review import export_package  # noqa: E402
from import_translation_review import import_reviews  # noqa: E402


def diagnostic(path):
    path.write_text(
        '{"results":[{"id":"synthetic-1","source":"tr","target":"en",'
        '"text":"3 kişi", "candidate_output":"3 people","route":["tr","en"],'
        '"protection_warnings":[]}]}',
        encoding="utf-8",
    )


def test_review_package_round_trip_and_tamper_detection(tmp_path):
    source = tmp_path / "diagnostic.json"
    diagnostic(source)
    csv_path, json_path = export_package(source, tmp_path / "package")
    assert json_path.exists()
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0].update(
        adequacy_1_5="4",
        meaning_preserved="yes",
        critical_error="no",
        numbers_correct="yes",
        names_addresses_correct="na",
        negation_correct="na",
        terminology_correct="yes",
        reviewer_native_language="tr",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    result = import_reviews(csv_path, tmp_path / "summary.json")
    assert result["overall"]["mean_adequacy"] == 4
    assert result["overall"]["critical_errors"] == 0

    rows[0]["machine_translation"] = "tampered"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="changed after export"):
        import_reviews(csv_path, tmp_path / "summary.json")
