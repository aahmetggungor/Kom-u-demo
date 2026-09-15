from copy import deepcopy

import pytest
from conftest import headers


def layer():
    return {
        "kind": "hospital",
        "name": "Synthetic hospital",
        "provenance": "Synthetic fixture, not an operational hospital",
        "geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Synthetic point"},
                    "geometry": {"type": "Point", "coordinates": [27.1, 38.4]},
                }
            ],
        },
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
    assert client.get("/api/v1/map/layers", headers=headers(other)).json() == []


@pytest.mark.parametrize("coordinates", [[181, 30], [25, 91], [True, 25], ["27", 38], [27, 38, 1]])
def test_invalid_layer_coordinates_rejected(setup, coordinates):
    _, client, admin, *_ = setup
    data = layer()
    data["geojson"]["features"][0]["geometry"]["coordinates"] = coordinates
    assert client.post("/api/v1/map/layers", headers=headers(admin), json=data).status_code == 422


def test_remote_and_excessive_layer_payloads_rejected(setup):
    _, client, admin, *_ = setup
    data = layer()
    data["geojson"]["features"][0]["properties"]["icon_url"] = "https://unexpected.example/private"
    assert client.post("/api/v1/map/layers", headers=headers(admin), json=data).status_code == 422
    data = layer()
    data["geojson"]["features"] = [deepcopy(data["geojson"]["features"][0]) for _ in range(201)]
    assert client.post("/api/v1/map/layers", headers=headers(admin), json=data).status_code in (
        413,
        422,
    )
