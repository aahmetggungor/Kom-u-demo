"""Synthetic event-group corpus, with explicit ground truth and deterministic UUIDs."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

templates = [
    (
        "rescue",
        "earthquake",
        "İzmir deprem sonrası enkaz altında 3 kişi mahsur. Yardım gerekiyor.",
        "Μετά τον σεισμό υπάρχουν 3 άνθρωποι εγκλωβισμένοι στα ερείπια. Χρειαζόμαστε βοήθεια.",
        "After the earthquake 3 people are trapped under rubble. Help is needed.",
    ),
    (
        "medical",
        "earthquake",
        "Deprem sonrası 2 yaralı var, ambulans gerekiyor.",
        "Μετά τον σεισμό υπάρχουν 2 τραυματίες, χρειαζόμαστε ασθενοφόρο.",
        "After the earthquake 2 people are injured, medical help needed.",
    ),
    (
        "water",
        "flood",
        "Sel sonrası içme suyu gerekiyor.",
        "Μετά την πλημμύρα χρειαζόμαστε νερό.",
        "After the flood we need drinking water.",
    ),
    (
        "shelter",
        "wildfire",
        "Orman yangını sonrası barınak gerekiyor.",
        "Μετά την πυρκαγιά χρειαζόμαστε καταφύγιο.",
        "After the wildfire we need shelter.",
    ),
]
rows = []
epoch = datetime(2026, 9, 14, 0, 0, tzinfo=UTC)
for group in range(1000):
    need, incident, *sentences = templates[group % len(templates)]
    for language, sentence in zip(["tr", "el", "en"], sentences, strict=True):
        rows.append(
            {
                "client_id": str(uuid5(NAMESPACE_URL, f"komsu-synthetic/{group}/{language}")),
                "text": sentence + f" [SYNTHETIC SITE {group:04d}]",
                "source": "android",
                "language": language,
                "occurred_at": (epoch + timedelta(seconds=group)).isoformat(),
                "address_raw": f"Synthetic training building {group:04d}; NOT A REAL ADDRESS",
                "location": {
                    "lat": 38.2 + (group % 20) * 0.005,
                    "lon": 26.8 + (group // 20) * 0.005,
                },
                "gold": {
                    "group": f"event-{group}",
                    "needs": [need],
                    "incident_type": incident,
                    "synthetic": True,
                    "scenario": "6.8 eastern Aegean earthquake exercise; flood/fire extensions",
                },
            }
        )
Path("data").mkdir(exist_ok=True)
Path("data/disaster.synthetic.jsonl").write_text(
    "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
)
print(f"Generated {len(rows)} synthetic reports in 1000 multilingual event groups")
