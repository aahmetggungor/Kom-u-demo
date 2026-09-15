import pytest
from fastapi.testclient import TestClient
from komsu.app import create_app
from komsu.cli import provision
from komsu.config import Settings
from komsu.db import make_engine
from komsu.models import Base


@pytest.fixture
def setup(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    admin = provision(engine, "Tenant A")
    other = provision(engine, "Tenant B")
    observer = provision(engine, "Observer", "observer", admin["tenant_id"])
    rescue = provision(engine, "Rescue", "rescue-team", admin["tenant_id"])
    settings = Settings(environment="test", requests_per_minute=10000, _env_file=None)
    with TestClient(create_app(settings, engine)) as client:
        yield engine, client, admin, other, observer, rescue
    engine.dispose()


def headers(identity):
    return {"Authorization": f"Bearer {identity['token']}"}
