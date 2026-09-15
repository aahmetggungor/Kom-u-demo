"""Small authored cross-language challenge; diagnostic, not field accuracy."""

import json
import time
from pathlib import Path

from komsu.ai import LocalBgeM3

texts = [
    "İzmir Atatürk Caddesi 12 numarada deprem sonrası üç kişi enkaz altında. Kurtarma ekibi gerekiyor.",
    "Three people are trapped under rubble after the earthquake at 12 Ataturk Street, Izmir. A rescue team is needed.",
    "Τρεις άνθρωποι έχουν παγιδευτεί στα ερείπια μετά τον σεισμό στην οδό Ατατούρκ 12, Σμύρνη. Χρειάζεται ομάδα διάσωσης.",
    "İzmir Atatürk Caddesi 98 numarada deprem sonrası üç kişi enkaz altında. Kurtarma ekibi gerekiyor.",
    "İzmir Atatürk Caddesi 12 numarada enkaz altında kimse yok. Kurtarma ekibi gerekmiyor.",
    "The shelter needs drinking water and baby food.",
]
started = time.perf_counter()
model = LocalBgeM3("models/bge-m3")
loaded = time.perf_counter()
vectors = model.encode(texts)
ended = time.perf_counter()
result = {
    "kind": "authored six-text diagnostic, not independent evaluation",
    "model": json.loads(Path("models/bge-m3/PROVENANCE.json").read_text()),
    "max_tokens": 512,
    "device": "CPU",
    "load_seconds": round(loaded - started, 3),
    "encode_seconds": round(ended - loaded, 3),
    "pairs": [
        {
            "source": texts[0],
            "candidate": candidate,
            "category": category,
            "cosine_similarity": round(
                sum(a * b for a, b in zip(vectors[0], vector, strict=True)), 6
            ),
        }
        for candidate, vector, category in zip(
            texts[1:],
            vectors[1:],
            [
                "same-event-en",
                "same-event-el",
                "different-building",
                "negated-need",
                "different-need",
            ],
            strict=True,
        )
    ],
    "limitations": "Semantic scores alone do not establish duplicate identity or negate a report. No calibrated threshold or field accuracy claimed.",
}
Path("docs/evaluation/bge-diagnostic.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {
            "load_seconds": result["load_seconds"],
            "encode_seconds": result["encode_seconds"],
            "scores": [(p["category"], p["cosine_similarity"]) for p in result["pairs"]],
        }
    )
)
