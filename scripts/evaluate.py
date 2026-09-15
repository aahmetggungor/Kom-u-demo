"""Report per-language heuristic regression; not a real-world accuracy claim."""

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from komsu.ai import BaselineAnalyzer


def ratio(a, b):
    return a / b if b else None


def evaluate(rows):
    by_language = defaultdict(
        lambda: {
            "n": 0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "exact": 0,
            "taxonomy_correct": 0,
            "latency_ms": [],
        }
    )
    analyzer = BaselineAnalyzer()
    for row in rows:
        start = time.perf_counter()
        result = analyzer.analyze(row["text"], row["language"], row.get("address_raw"))
        m = by_language[row["language"]]
        m["n"] += 1
        expected = set(row["gold"]["needs"])
        actual = set(result["needs"])
        m["tp"] += len(expected & actual)
        m["fp"] += len(actual - expected)
        m["fn"] += len(expected - actual)
        m["exact"] += expected == actual
        m["taxonomy_correct"] += result["incident_type"] == row["gold"]["incident_type"]
        m["latency_ms"].append((time.perf_counter() - start) * 1000)
    output = {}
    for lang, m in by_language.items():
        output[lang] = {
            "samples": m["n"],
            "need_precision_micro": ratio(m["tp"], m["tp"] + m["fp"]),
            "need_recall_micro": ratio(m["tp"], m["tp"] + m["fn"]),
            "need_f1_micro": ratio(2 * m["tp"], 2 * m["tp"] + m["fp"] + m["fn"]),
            "need_false_negative_rate": ratio(m["fn"], m["tp"] + m["fn"]),
            "need_exact_match": ratio(m["exact"], m["n"]),
            "taxonomy_accuracy": ratio(m["taxonomy_correct"], m["n"]),
            "inference_median_ms": statistics.median(m["latency_ms"]),
            "false_positives": m["fp"],
            "false_negatives": m["fn"],
        }
    return {
        "kind": "synthetic_template_regression_only",
        "pipeline": "rules-0.1",
        "languages": output,
        "location_accuracy": None,
        "duplicate_precision": None,
        "duplicate_recall": None,
        "translation_quality": None,
        "time_to_triage": None,
        "unmeasured_reason": "No active location/semantic/translation model or end-to-end benchmark in this script; template fit is not field performance.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/disaster.synthetic.jsonl")
    parser.add_argument("--output", default="docs/evaluation/baseline-results.json")
    parser.add_argument("--kind", default="synthetic_template_regression_only")
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines()]
    result = evaluate(rows)
    result["kind"] = args.kind
    Path("docs/evaluation").mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
