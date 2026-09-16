"""Compare need classifiers on disclosed synthetic development/test partitions."""

import hashlib
import json
import re
from pathlib import Path

from komsu.ai import BaselineAnalyzer, GuardedRulesAnalyzer

NEEDS = ("rescue", "medical", "shelter", "water", "food")
TRAIN = Path("data/disaster.synthetic.jsonl")
DEVELOPMENT = Path("data/challenge.synthetic.jsonl")
TEST = Path("data/classification-holdout.synthetic.jsonl")


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def metrics(rows, predictions):
    scopes = {"overall": list(range(len(rows)))}
    scopes.update(
        {
            language: [i for i, row in enumerate(rows) if row["language"] == language]
            for language in ("tr", "el", "en")
        }
    )
    output = {}
    for scope, indices in scopes.items():
        tp = fp = fn = exact = urgency_correct = critical_fn = 0
        per_need = {need: {"tp": 0, "fp": 0, "fn": 0} for need in NEEDS}
        for index in indices:
            row, prediction = rows[index], predictions[index]
            expected, actual = set(row["gold"]["needs"]), set(prediction["needs"])
            tp += len(expected & actual)
            fp += len(actual - expected)
            fn += len(expected - actual)
            exact += expected == actual
            urgency_correct += prediction["urgency_level"] == row["gold"]["urgency_level"]
            if (
                row["gold"]["urgency_level"] == "CRITICAL"
                and prediction["urgency_level"] != "CRITICAL"
            ):
                critical_fn += 1
            for need in NEEDS:
                per_need[need]["tp"] += need in expected and need in actual
                per_need[need]["fp"] += need not in expected and need in actual
                per_need[need]["fn"] += need in expected and need not in actual
        output[scope] = {
            "samples": len(indices),
            "need_precision_micro": safe_ratio(tp, tp + fp),
            "need_recall_micro": safe_ratio(tp, tp + fn),
            "need_f1_micro": safe_ratio(2 * tp, 2 * tp + fp + fn),
            "need_false_negative_rate": safe_ratio(fn, tp + fn),
            "need_exact_match": safe_ratio(exact, len(indices)),
            "urgency_accuracy": safe_ratio(urgency_correct, len(indices)),
            "critical_urgency_false_negatives": critical_fn,
            "per_need": {
                need: {
                    **counts,
                    "precision": safe_ratio(counts["tp"], counts["tp"] + counts["fp"]),
                    "recall": safe_ratio(counts["tp"], counts["tp"] + counts["fn"]),
                }
                for need, counts in per_need.items()
            },
        }
    output["failures"] = [
        {
            "id": row.get("id", f"development-{index + 1}"),
            "language": row["language"],
            "tags": row.get("tags", []),
            "expected_needs": row["gold"]["needs"],
            "actual_needs": prediction["needs"],
            "expected_urgency": row["gold"].get("urgency_level"),
            "actual_urgency": prediction["urgency_level"],
        }
        for index, (row, prediction) in enumerate(zip(rows, predictions, strict=True))
        if set(row["gold"]["needs"]) != set(prediction["needs"])
        or row["gold"].get("urgency_level") != prediction["urgency_level"]
    ]
    tags = sorted({tag for row in rows for tag in row.get("tags", [])})
    output["by_error_tag"] = {}
    for tag in tags:
        indices = [index for index, row in enumerate(rows) if tag in row.get("tags", [])]
        false_positives = false_negatives = incorrect_rows = urgency_errors = 0
        for index in indices:
            expected = set(rows[index]["gold"]["needs"])
            actual = set(predictions[index]["needs"])
            false_positives += len(actual - expected)
            false_negatives += len(expected - actual)
            incorrect_rows += expected != actual
            urgency_errors += (
                rows[index]["gold"].get("urgency_level") != predictions[index]["urgency_level"]
            )
        output["by_error_tag"][tag] = {
            "samples": len(indices),
            "incorrect_rows": incorrect_rows,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "urgency_errors": urgency_errors,
        }
    return output


def urgency(needs):
    return (
        "CRITICAL"
        if "rescue" in needs
        else "HIGH"
        if "medical" in needs
        else "MEDIUM"
        if needs
        else "UNKNOWN"
    )


class CharacterLogisticCandidate:
    def __init__(self, training, development):
        import sklearn
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        self.sklearn_version = sklearn.__version__
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=30_000, sublinear_tf=True
        )

        def clean(text):
            return re.sub(r"\s*\[SYNTHETIC SITE \d+\]", "", text)

        matrix = self.vectorizer.fit_transform([clean(row["text"]) for row in training])
        self.models = {}
        for need in NEEDS:
            labels = [int(need in row["gold"]["needs"]) for row in training]
            if len(set(labels)) == 1:
                self.models[need] = labels[0]
            else:
                self.models[need] = LogisticRegression(
                    class_weight="balanced", max_iter=500, random_state=42
                ).fit(matrix, labels)
        development_scores = self.scores([row["text"] for row in development])
        best = None
        for threshold in [value / 20 for value in range(2, 19)]:
            predictions = self.predict_scores(development_scores, threshold)
            result = metrics(
                [
                    {**row, "gold": {**row["gold"], "urgency_level": urgency(row["gold"]["needs"])}}
                    for row in development
                ],
                predictions,
            )["overall"]
            score = (result["need_f1_micro"], result["need_recall_micro"], -threshold)
            if best is None or score > best[0]:
                best = (score, threshold)
        self.threshold = best[1]

    def scores(self, texts):
        matrix = self.vectorizer.transform(texts)
        return [
            {
                need: float(
                    model if isinstance(model, int) else model.predict_proba(matrix[index])[0, 1]
                )
                for need, model in self.models.items()
            }
            for index in range(len(texts))
        ]

    @staticmethod
    def predict_scores(scores, threshold):
        return [
            {
                "needs": [need for need in NEEDS if row[need] >= threshold],
                "urgency_level": urgency([need for need in NEEDS if row[need] >= threshold]),
                "human_review_required": True,
            }
            for row in scores
        ]

    def predict(self, rows):
        return self.predict_scores(self.scores([row["text"] for row in rows]), self.threshold)


def main():
    training_all, development, test = load(TRAIN), load(DEVELOPMENT), load(TEST)
    training, internal_validation = [], []
    for row in training_all:
        target = (
            internal_validation if int(row["gold"]["group"].split("-")[1]) % 5 == 0 else training
        )
        target.append(row)
    analyzers = {
        "rules-0.1": BaselineAnalyzer(),
        "rules-0.2-candidate": GuardedRulesAnalyzer(),
    }
    results = {}
    development_with_urgency = [
        {**row, "gold": {**row["gold"], "urgency_level": urgency(row["gold"]["needs"])}}
        for row in development
    ]
    for name, analyzer in analyzers.items():
        results[name] = {
            "development": metrics(
                development_with_urgency,
                [analyzer.analyze(row["text"], row["language"]) for row in development],
            ),
            "authored_holdout": metrics(
                test, [analyzer.analyze(row["text"], row["language"]) for row in test]
            ),
        }
    model = CharacterLogisticCandidate(training, development)
    results["char-tfidf-logistic-candidate"] = {
        "development": metrics(development_with_urgency, model.predict(development)),
        "authored_holdout": metrics(test, model.predict(test)),
    }
    output = {
        "kind": "authored_synthetic_candidate_comparison_not_independent_validation",
        "default_runtime_analyzer": "rules-0.1",
        "default_changed": False,
        "decision": "NO_CHANGE_PENDING_INDEPENDENT_NATIVE_SPEAKER_FIELD_VALIDATION",
        "safety_thresholds": {
            "overall_precision_min": 0.85,
            "overall_recall_min": 0.85,
            "per_language_recall_min": 0.80,
            "rescue_medical_recall_min": 0.90,
            "urgency_accuracy_min": 0.85,
            "numbered_critical_false_negatives_max": 0,
        },
        "data": {
            "training": {"path": str(TRAIN), "sha256": digest(TRAIN), "rows": len(training)},
            "internal_validation": {"rows": len(internal_validation)},
            "development": {
                "path": str(DEVELOPMENT),
                "sha256": digest(DEVELOPMENT),
                "rows": len(development),
            },
            "authored_holdout": {"path": str(TEST), "sha256": digest(TEST), "rows": len(test)},
            "split_rule": "gold.group numeric suffix modulo 5; all TR/EL/EN event variants stay together",
        },
        "model_provenance": {
            "library": "scikit-learn",
            "version": model.sklearn_version,
            "features": "character TF-IDF word-boundary 3..5 grams; max_features=30000",
            "classifier": "per-need class-balanced LogisticRegression random_state=42",
            "threshold_selected_on_development_only": model.threshold,
            "remote_inference": False,
        },
        "results": results,
        "limitations": [
            "The template training corpus has only four repeated positive classes and no food examples.",
            "The authored holdout and candidate rules share an author and are not independent.",
            "Greek wording and every label require native-speaker and rescue-domain review.",
            "No result authorizes suppression, merging or dispatch; human review remains mandatory.",
        ],
    }
    target = Path("docs/evaluation/classification-candidate-results.json")
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"output": str(target), "decision": output["decision"], "threshold": model.threshold}
        )
    )


if __name__ == "__main__":
    main()
