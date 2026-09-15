"""Template-corpus semantic retrieval diagnostic with hard same-template negatives."""

import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from komsu.ai import LocalBgeM3, duplicate_evidence

EVENTS = 80
MARKER = re.compile(r"\s*\[SYNTHETIC SITE \d+\]\s*$")


def confusion(labels, predictions):
    tp = sum(a and b for a, b in zip(labels, predictions, strict=True))
    fp = sum(not a and b for a, b in zip(labels, predictions, strict=True))
    fn = sum(a and not b for a, b in zip(labels, predictions, strict=True))
    tn = len(labels) - tp - fp - fn
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(tp / max(1, tp + fp), 4),
        "recall": round(tp / max(1, tp + fn), 4),
    }


def metres(a, b):
    # Adequate for this small synthetic coordinate grid; not application geodesy.
    lat = (a["location"]["lat"] + b["location"]["lat"]) / 2
    dy = (a["location"]["lat"] - b["location"]["lat"]) * 111_320
    dx = (a["location"]["lon"] - b["location"]["lon"]) * 111_320 * np.cos(np.radians(lat))
    return float(np.hypot(dx, dy))


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

    started = time.perf_counter()
    model = LocalBgeM3("models/bge-m3")
    loaded = time.perf_counter()
    vectors = np.asarray(model.encode([row["text_for_embedding"] for row in rows]))
    encoded = time.perf_counter()
    similarities = vectors @ vectors.T
    np.fill_diagonal(similarities, -2)

    retrieval = {}
    for language in ("tr", "el", "en"):
        indices = [i for i, row in enumerate(rows) if row["language"] == language]
        hits = sum(
            rows[int(np.argmax(similarities[index]))]["gold"]["group"]
            == rows[index]["gold"]["group"]
            for index in indices
        )
        retrieval[language] = {
            "queries": len(indices),
            "recall_at_1": round(hits / len(indices), 4),
        }

    pairs = []
    for event in range(EVENTS):
        base = event * 3
        for left, right in ((0, 1), (0, 2), (1, 2)):
            pairs.append((base + left, base + right, True, "same-event-cross-language"))
    for event in range(EVENTS - 4):
        for language_offset in range(3):
            pairs.append(
                (
                    event * 3 + language_offset,
                    (event + 4) * 3 + language_offset,
                    False,
                    "different-event-same-template-language",
                )
            )

    labels = [same for _, _, same, _ in pairs]
    scores = [float(similarities[left, right]) for left, right, _, _ in pairs]
    thresholds = {
        str(value): confusion(labels, [score >= value for score in scores])
        for value in (0.70, 0.80, 0.85, 0.90, 0.92, 0.95)
    }
    combined = []
    for left, right, same, _ in pairs:
        a, b = rows[left], rows[right]
        seconds = abs(
            (
                datetime.fromisoformat(a["occurred_at"]) - datetime.fromisoformat(b["occurred_at"])
            ).total_seconds()
        )
        evidence = duplicate_evidence(
            max(-1.0, min(1.0, float(similarities[left, right]))),
            metres(a, b),
            seconds,
            same_building=same,
            conflicting_entities=a["gold"]["needs"] != b["gold"]["needs"],
        )
        combined.append(evidence.propose_merge)

    false_candidates = sorted(
        (
            {
                "score": round(score, 6),
                "left_group": rows[left]["gold"]["group"],
                "right_group": rows[right]["gold"]["group"],
                "language": rows[left]["language"],
                "needs": rows[left]["gold"]["needs"],
            }
            for (left, right, same, _), score in zip(pairs, scores, strict=True)
            if not same
        ),
        key=lambda row: row["score"],
        reverse=True,
    )[:10]
    positives = [score for score, label in zip(scores, labels, strict=True) if label]
    negatives = [score for score, label in zip(scores, labels, strict=True) if not label]
    result = {
        "kind": "development-template-corpus-diagnostic-not-independent-validation",
        "events": EVENTS,
        "messages": len(rows),
        "languages": ["tr", "el", "en"],
        "synthetic_site_marker_removed_before_embedding": True,
        "model_revision": json.loads(Path("models/bge-m3/PROVENANCE.json").read_text())["revision"],
        "load_seconds": round(loaded - started, 3),
        "encode_seconds": round(encoded - loaded, 3),
        "retrieval": retrieval,
        "pair_counts": {"positive": len(positives), "hard_negative": len(negatives)},
        "score_percentiles": {
            "positive": {str(p): round(float(np.percentile(positives, p)), 6) for p in (5, 50, 95)},
            "hard_negative": {
                str(p): round(float(np.percentile(negatives, p)), 6) for p in (5, 50, 95)
            },
        },
        "semantic_thresholds_balanced_development_pairs": thresholds,
        "combined_metadata_gate": confusion(labels, combined),
        "highest_hard_negatives": false_candidates,
        "limitations": (
            "Corpus templates were used during development and repeat wording. Pair prevalence is artificial. "
            "Same-building truth is supplied directly to the metadata gate; real building identity extraction "
            "is not implemented. No threshold authorizes automatic merge."
        ),
    }
    Path("docs/evaluation/duplicate-retrieval-diagnostic.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
