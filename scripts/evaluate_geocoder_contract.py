"""Measure the local synthetic geocoder contract; this is not live provider evidence."""

import json
import math
import threading
from collections import defaultdict
from pathlib import Path

from geocoder_contract_server import create_server, load_rows
from komsu.geolocation import NominatimSelfHosted, location_annotation


def metres(a_lat, a_lon, b_lat, b_lon):
    lat = (a_lat + b_lat) / 2
    dy = (a_lat - b_lat) * 111_320
    dx = (a_lon - b_lon) * 111_320 * math.cos(math.radians(lat))
    return math.hypot(dx, dy)


def main() -> None:
    fixture = Path("data/geocoder-gold.synthetic.jsonl")
    rows = load_rows(fixture)
    server = create_server(0, fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = NominatimSelfHosted(f"http://127.0.0.1:{server.server_port}", requests_per_second=50)
    results = []
    try:
        for row in rows:
            candidates = provider.candidates("synthetic-evaluation", row["query"], row["language"])
            top = candidates[0] if candidates else None
            annotation = location_annotation(candidates)
            results.append(
                {
                    "id": row["id"],
                    "language": row["language"],
                    "tags": row["tags"],
                    "top1_provider_correct": bool(top and top.provider_id == row["provider_id"]),
                    "precision_correct": bool(top and top.precision == row["precision"]),
                    "error_m": round(metres(top.lat, top.lon, row["lat"], row["lon"]), 3)
                    if top
                    else None,
                    "location_status": annotation["location_status"],
                }
            )
    finally:
        provider.client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    by_language = defaultdict(list)
    for result in results:
        by_language[result["language"]].append(result)

    def summary(values):
        errors = [value["error_m"] for value in values if value["error_m"] is not None]
        return {
            "cases": len(values),
            "top1_accuracy": round(
                sum(v["top1_provider_correct"] for v in values) / len(values), 4
            ),
            "precision_accuracy": round(
                sum(v["precision_correct"] for v in values) / len(values), 4
            ),
            "median_error_m": sorted(errors)[len(errors) // 2] if errors else None,
            "unresolved_fraction": round(
                sum(v["error_m"] is None for v in values) / len(values), 4
            ),
        }

    output = {
        "kind": "synthetic-localhost-contract-not-live-geocoder-validation",
        "overall": summary(results),
        "by_language": {language: summary(values) for language, values in by_language.items()},
        "results": results,
        "limitations": "Queries map exactly to authored contract fixtures, including authored typo aliases. No municipal index, network SLA, real ambiguity or field address accuracy is measured.",
    }
    Path("docs/evaluation/geocoder-contract-results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(output["overall"]))


if __name__ == "__main__":
    main()
