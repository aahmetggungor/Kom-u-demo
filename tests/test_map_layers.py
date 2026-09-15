from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from conftest import headers
from komsu.map_layers import canonical_geojson_sha256


def layer(kind="hospital", geometry=None):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Synthetic point"},
                "geometry": geometry or {"type": "Point", "coordinates": [27.1, 38.4]},
            }
        ],
    }
    return {
        "kind": kind,
        "name": "Synthetic hospital",
        "provenance": "Synthetic fixture, not an operational hospital",
        "dataset_version": "synthetic-1",
        "license_name": "Synthetic test fixture",
        "content_sha256": canonical_geojson_sha256(geojson),
        "source_updated_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        "stale_after_days": 30,
        "geojson": geojson,
    }


def test_layer_admin_only_and_tenant_isolation(setup):
    _, client, admin, other, observer, _ = setup
    assert (
        client.post("/api/v1/map/layers", headers=headers(observer), json=layer()).status_code
        == 403
    )
    response = client.post("/api/v1/map/layers", headers=headers(admin), json=layer())
    assert response.status_code == 201
    visible = client.get("/api/v1/map/layers", headers=headers(observer)).json()
    assert len(visible) == 1 and visible[0]["provenance"] == layer()["provenance"]
    assert visible[0]["dataset_version"] == "synthetic-1" and not visible[0]["is_stale"]
    assert client.get("/api/v1/map/layers", headers=headers(other)).json() == []
    package = client.get("/api/v1/map/package", headers=headers(observer)).json()
    assert package == {"enabled": False, "reason": "MAP_PACKAGE_NOT_CONFIGURED"}


@pytest.mark.parametrize("coordinates", [[181, 30], [25, 91], [True, 25], ["27", 38], [27, 38, 1]])
def test_invalid_layer_coordinates_rejected(setup, coordinates):
    _, client, admin, *_ = setup
    data = layer()
    data["geojson"]["features"][0]["geometry"]["coordinates"] = coordinates
    data["content_sha256"] = canonical_geojson_sha256(data["geojson"])
    assert client.post("/api/v1/map/layers", headers=headers(admin), json=data).status_code == 422


def test_remote_and_excessive_layer_payloads_rejected(setup):
    _, client, admin, *_ = setup
    data = layer()
    data["geojson"]["features"][0]["properties"]["icon_url"] = "https://unexpected.example/private"
    data["content_sha256"] = canonical_geojson_sha256(data["geojson"])
    assert client.post("/api/v1/map/layers", headers=headers(admin), json=data).status_code == 422
    data = layer()
    data["geojson"]["features"] = [deepcopy(data["geojson"]["features"][0]) for _ in range(201)]
    data["content_sha256"] = canonical_geojson_sha256(data["geojson"])
    assert client.post("/api/v1/map/layers", headers=headers(admin), json=data).status_code in (
        413,
        422,
    )


def test_polygon_multi_geometry_and_checksum_controls(setup):
    _, client, admin, *_ = setup
    polygon = {
        "type": "Polygon",
        "coordinates": [[[27.0, 38.0], [27.1, 38.0], [27.1, 38.1], [27.0, 38.0]]],
    }
    assert (
        client.post(
            "/api/v1/map/layers", headers=headers(admin), json=layer("shelter", polygon)
        ).status_code
        == 201
    )
    multiline = {
        "type": "MultiLineString",
        "coordinates": [[[27.0, 38.0], [27.1, 38.1]], [[27.2, 38.2], [27.3, 38.3]]],
    }
    assert (
        client.post(
            "/api/v1/map/layers", headers=headers(admin), json=layer("closed_road", multiline)
        ).status_code
        == 201
    )
    bad = layer("shelter", polygon)
    bad["content_sha256"] = "0" * 64
    assert client.post("/api/v1/map/layers", headers=headers(admin), json=bad).status_code == 422
    incompatible = layer("hospital", multiline)
    assert (
        client.post("/api/v1/map/layers", headers=headers(admin), json=incompatible).status_code
        == 422
    )
