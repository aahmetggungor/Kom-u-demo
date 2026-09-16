import pytest
from fastapi.testclient import TestClient
from komsu.config import Settings
from komsu.render_demo import create_demo_app


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


def test_demo_requires_strong_password(setup, tmp_path):
    with pytest.raises(RuntimeError, match="24 characters"):
        create_demo_app(
            Settings(environment="test", _env_file=None),
            setup[0],
            password="short",
            static_dir=tmp_path,
        )
