from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from komsu.config import Settings
from komsu.render_demo import create_demo_app, validate_demo_password


def test_demo_login_rejects_and_limits_attempts(setup, tmp_path):
    engine = setup[0]
    (tmp_path / "index.html").write_text("Synthetic demo", encoding="utf-8")
    app = create_demo_app(
        Settings(environment="test", _env_file=None), engine, password="x" * 32, static_dir=tmp_path
    )
    with TestClient(app) as client:
        assert client.get("/").text == "Synthetic demo"
        assert client.get("/api/v1/cases").status_code == 401
        assert client.post("/api/v1/demo/session", json={"password": "wrong"}).status_code == 401
        for _ in range(9):
            assert (
                client.post("/api/v1/demo/session", json={"password": "wrong"}).status_code == 401
            )
        assert client.post("/api/v1/demo/session", json={"password": "x" * 32}).status_code == 429


@pytest.mark.parametrize("password", ["", "123", "x" * 257])
def test_demo_requires_bounded_password(setup, tmp_path, password):
    with pytest.raises(RuntimeError, match="4 to 256 characters"):
        create_demo_app(
            Settings(environment="test", _env_file=None),
            setup[0],
            password=password,
            static_dir=tmp_path,
        )


def test_demo_short_password_keeps_login_required(setup, tmp_path):
    (tmp_path / "index.html").write_text("Synthetic demo", encoding="utf-8")
    validate_demo_password("1234")
    validate_demo_password("x" * 256)
    app = create_demo_app(
        Settings(environment="test", _env_file=None),
        setup[0],
        password="1234",
        static_dir=tmp_path,
    )
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/v1/cases").status_code == 401
        assert client.post("/api/v1/demo/session", json={"password": "wrong"}).status_code == 401
        with patch.object(app.state, "engine"):
            response = client.post("/api/v1/demo/session", json={"password": "1234"})
        assert response.status_code == 200
        assert response.json()["expires_in"] == 28800
        assert len(response.json()["token"]) >= 32
