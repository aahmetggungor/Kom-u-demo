"""Import conspicuously synthetic GIS fixtures into the local demo tenant, once per name."""

import json
from pathlib import Path

import httpx

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
        ("assembly", "SENTETİK · Toplanma örneği", {"type": "Point", "coordinates": [27.3, 38.3]}),
        ("shelter", "SENTETİK · Barınak örneği", {"type": "Point", "coordinates": [26.9, 38.2]}),
        (
            "closed_road",
            "SENTETİK · Kapalı yol örneği",
            {"type": "LineString", "coordinates": [[27.0, 38.25], [27.2, 38.3]]},
        ),
    ]:
        if title in names:
            continue
        response = client.post(
            "/map/layers",
            json={
                "name": title,
                "kind": kind,
                "provenance": "Yapay eğitim verisi; gerçek tesis veya yol durumu değildir.",
                "geojson": {
                    "type": "FeatureCollection",
                    "features": [
                        {"type": "Feature", "properties": {"name": title}, "geometry": geometry}
                    ],
                },
            },
        )
        response.raise_for_status()
print("Synthetic GIS layers are available; they do not represent real facilities or road status.")
