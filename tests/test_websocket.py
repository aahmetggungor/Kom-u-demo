import pytest
from starlette.websockets import WebSocketDisconnect


@pytest.mark.parametrize(
    "hello", [[], None, "text", {"token": "x", "after": True}, {"token": "x", "after": -1}]
)
def test_malformed_first_frame_closes_without_data(setup, hello):
    _, client, *_ = setup
    with client.websocket_connect(
        "/api/v1/events/ws", headers={"origin": "http://127.0.0.1:5173"}
    ) as ws:
        ws.send_json(hello)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008


def test_websocket_valid_auth_and_origin_rejection(setup):
    _, client, admin, *_ = setup
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/v1/events/ws", headers={"origin": "https://unexpected.example"}
        ):
            pass
    with client.websocket_connect(
        "/api/v1/events/ws", headers={"origin": "http://127.0.0.1:5173"}
    ) as ws:
        ws.send_json({"token": admin["token"], "after": 0})
        assert ws.receive_json() == {"items": [], "type": "heartbeat"}
