"""Import conspicuously synthetic GIS fixtures into the local demo tenant, once per name."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from komsu.map_layers import canonical_geojson_sha256

identity = json.loads(Path(".env.session.json").read_text(encoding="utf-8"))
with httpx.Client(
    base_url="http://127.0.0.1:8000/api/v1",
    headers={"Authorization": "Bearer " + identity["token"]},
    trust_env=False,
    timeout=10,
) as client:
    existing = client.get("/map/layers")
    existing.raise_for_status()
    names = {row["name"] for row in existing.json()}
    for kind, title, geometry in [
        ("hospital", "SENTETİK · Hastane örneği", {"type": "Point", "coordinates": [27.1, 38.4]}),
        (
            "assembly",
            "SENTETİK · Toplanma örneği",
            {
                "type": "Polygon",
                "coordinates": [[[27.29, 38.29], [27.31, 38.29], [27.31, 38.31], [27.29, 38.29]]],
            },
        ),
        (
            "shelter",
            "SENTETİK · Barınak örneği",
            {"type": "MultiPoint", "coordinates": [[26.9, 38.2], [26.91, 38.21]]},
        ),
        (
            "closed_road",
            "SENTETİK · Kapalı yol örneği",
            {"type": "LineString", "coordinates": [[27.0, 38.25], [27.2, 38.3]]},
        ),
    ]:
        if title in names:
            continue
        geojson = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"name": title}, "geometry": geometry}],
        }
        response = client.post(
            "/map/layers",
            json={
                "name": title,
                "kind": kind,
                "provenance": "Yapay eğitim verisi; gerçek tesis veya yol durumu değildir.",
                "dataset_version": "synthetic-demo-2",
                "license_name": "Komşu synthetic test fixture",
                "content_sha256": canonical_geojson_sha256(geojson),
                "source_updated_at": datetime.now(UTC).isoformat(),
                "stale_after_days": 30,
                "geojson": geojson,
            },
        )
        response.raise_for_status()
print("Synthetic GIS layers are available; they do not represent real facilities or road status.")
