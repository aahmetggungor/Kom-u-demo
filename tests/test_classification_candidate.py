import json
from pathlib import Path

from komsu.ai import BaselineAnalyzer, GuardedRulesAnalyzer
from komsu.pipeline import Pipeline, ValidatedAnalysis

ROOT = Path(__file__).parents[1]


def load_holdout():
    return [
        json.loads(line)
        for line in (ROOT / "data/classification-holdout.synthetic.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]


def test_authored_holdout_has_disjoint_ids_and_required_safety_slices():
    rows = load_holdout()
    assert len(rows) == 36 and len({row["id"] for row in rows}) == 36
    assert {row["language"] for row in rows} == {"tr", "el", "en"}
    assert all(
        sum(row["language"] == language for row in rows) == 12 for language in ("tr", "el", "en")
    )
    assert {need for row in rows for need in row["gold"]["needs"]} == {
        "rescue",
        "medical",
        "shelter",
        "water",
        "food",
    }
    assert {tag for row in rows for tag in row["tags"]} >= {
        "negation",
        "implicit",
        "number",
        "ambiguous",
        "ended_exercise",
    }


def test_guarded_candidate_preserves_synthetic_safety_slices_without_automation():
    analyzer = GuardedRulesAnalyzer()
    for row in load_holdout():
        result = ValidatedAnalysis.model_validate(analyzer.analyze(row["text"], row["language"]))
        assert set(result.needs) == set(row["gold"]["needs"]), row["id"]
        assert result.urgency_level == row["gold"]["urgency_level"], row["id"]
        assert result.human_review_required is True
        if "number" in row["tags"]:
            assert "NUMERALS_REQUIRE_REVIEW" in result.warnings
        if "ambiguous" in row["tags"]:
            assert "AMBIGUOUS_STATEMENT_REQUIRES_REVIEW" in result.warnings


def test_deployed_default_is_not_silently_promoted_from_authored_results():
    assert isinstance(Pipeline("synthetic-tenant").analyzer, BaselineAnalyzer)
    result = Pipeline("synthetic-tenant").analyze("We have nothing left to drink.", "en", None)
    assert result["needs"] == []
    assert result["human_review_required"] is True
