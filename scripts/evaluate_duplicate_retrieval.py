"""Evaluate explainable duplicate suggestions on separate synthetic dev/test events."""

import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from komsu.ai import LocalBgeM3, multi_signal_duplicate_evidence

EVENTS = 120
DEV_EVENTS = frozenset(range(60))
TEST_EVENTS = frozenset(range(60, 120))
MARKER = re.compile(r"\s*\[SYNTHETIC SITE \d+\]\s*$")
THRESHOLDS = (0.55, 0.60, 0.65, 0.68, 0.70, 0.75, 0.80, 0.85)


def confusion(labels, predictions):
    tp = sum(a and b for a, b in zip(labels, predictions, strict=True))
    fp = sum(not a and b for a, b in zip(labels, predictions, strict=True))
    fn = sum(a and not b for a, b in zip(labels, predictions, strict=True))
    tn = len(labels) - tp - fp - fn
    precision, recall = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / max(1e-12, precision + recall), 4),
        "false_merge_rate": round(fp / max(1, fp + tn), 4),
    }


def metres(a, b):
    lat = (a["location"]["lat"] + b["location"]["lat"]) / 2
    dy = (a["location"]["lat"] - b["location"]["lat"]) * 111_320
    dx = (a["location"]["lon"] - b["location"]["lon"]) * 111_320 * np.cos(np.radians(lat))
    return float(np.hypot(dx, dy))


def build_pairs(event_ids, grouped, row_index):
    pairs, ordered = [], sorted(event_ids)
    for event in ordered:
        for left in grouped[event]:
            for right in grouped[event]:
                if left["language"] != right["language"]:
                    pairs.append(
                        (row_index[id(left)], row_index[id(right)], True, left["language"])
                    )
    allowed = set(ordered)
    for event in ordered:
        if event + 4 not in allowed:
            continue
        a = {row["language"]: row for row in grouped[event]}
        b = {row["language"]: row for row in grouped[event + 4]}
        for language in ("tr", "el", "en"):
            pairs.append((row_index[id(a[language])], row_index[id(b[language])], False, language))
    return pairs


def score_pairs(pairs, rows, similarities):
    scored = []
    for left, right, label, language in pairs:
        a, b = rows[left], rows[right]
        distance = metres(a, b)
        seconds = abs(
            (
                datetime.fromisoformat(a["occurred_at"]) - datetime.fromisoformat(b["occurred_at"])
            ).total_seconds()
        )
        evidence = multi_signal_duplicate_evidence(
            max(-1.0, min(1.0, float(similarities[left, right]))),
            distance,
            seconds,
            a["address_raw"],
            b["address_raw"],
            a["gold"]["needs"],
            b["gold"]["needs"],
            "REPORTED_OR_MIXED",
        )
        scored.append(
            {
                "label": label,
                "language": language,
                "score": evidence.score,
                "eligible": not evidence.blockers
                and (evidence.entity_similarity >= 0.75 or distance <= 50),
                "runtime_suggestion": evidence.propose_merge,
                "blockers": list(evidence.blockers),
                "semantic": evidence.semantic_similarity,
                "left_group": a["gold"]["group"],
                "right_group": b["gold"]["group"],
            }
        )
    return scored


def metrics(rows, threshold):
    result = confusion(
        [row["label"] for row in rows],
        [row["eligible"] and row["score"] >= threshold for row in rows],
    )
    result["by_language"] = {
        language: confusion(
            [row["label"] for row in rows if row["language"] == language],
            [
                row["eligible"] and row["score"] >= threshold
                for row in rows
                if row["language"] == language
            ],
        )
        for language in ("tr", "el", "en")
    }
    return result


def main() -> None:
    grouped = defaultdict(list)
    with Path("data/disaster.synthetic.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            number = int(row["gold"]["group"].split("-")[1])
            if number < EVENTS:
                row["text_for_embedding"] = MARKER.sub("", row["text"])
                grouped[number].append(row)
    rows = [row for number in range(EVENTS) for row in grouped[number]]
    if len(rows) != EVENTS * 3 or any(len(grouped[number]) != 3 for number in range(EVENTS)):
        raise RuntimeError("Expected exactly three languages per selected synthetic event")
    row_index = {id(row): index for index, row in enumerate(rows)}
    started = time.perf_counter()
    model = LocalBgeM3("models/bge-m3")
    loaded = time.perf_counter()
    vectors = np.asarray(model.encode([row["text_for_embedding"] for row in rows]))
    encoded = time.perf_counter()
    similarities = vectors @ vectors.T
    dev = score_pairs(build_pairs(DEV_EVENTS, grouped, row_index), rows, similarities)
    test = score_pairs(build_pairs(TEST_EVENTS, grouped, row_index), rows, similarities)
    development = {str(value): metrics(dev, value) for value in THRESHOLDS}
    candidates = [value for value in THRESHOLDS if development[str(value)]["false_merge_rate"] == 0]
    selected = max(
        candidates,
        key=lambda value: (development[str(value)]["f1"], development[str(value)]["recall"], value),
    )
    hard_negatives = sorted(
        (row for row in test if not row["label"]), key=lambda row: row["semantic"], reverse=True
    )[:10]
    result = {
        "kind": "same-author-synthetic-multisignal-diagnostic-not-independent-validation",
        "events": {"development": 60, "test": 60},
        "messages": len(rows),
        "pair_counts": {
            "development": {
                "positive": sum(r["label"] for r in dev),
                "negative": sum(not r["label"] for r in dev),
            },
            "test": {
                "positive": sum(r["label"] for r in test),
                "negative": sum(not r["label"] for r in test),
            },
        },
        "model_revision": json.loads(Path("models/bge-m3/PROVENANCE.json").read_text())["revision"],
        "load_seconds": round(loaded - started, 3),
        "encode_seconds": round(encoded - loaded, 3),
        "threshold_selection_rule": "zero development false merges, then highest F1, recall, threshold",
        "development_thresholds": development,
        "selected_threshold": selected,
        "held_out_test": metrics(test, selected),
        "runtime_threshold_0_68_test": metrics(test, 0.68),
        "highest_semantic_hard_negatives": hard_negatives,
        "promotion_decision": "NOT_PROMOTED_SAME_AUTHOR_SYNTHETIC_ADDRESS_MARKERS",
        "limitations": "Development and test events are disjoint but come from the same repeated template generator. Addresses expose synthetic building numbers and reported coordinates are exact fixtures. The score only creates explainable human-review candidates; it never merges cases.",
    }
    Path("docs/evaluation/duplicate-retrieval-diagnostic.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"selected_threshold": selected, "held_out_test": result["held_out_test"]}))


if __name__ == "__main__":
    main()
