import base64
import hashlib
import hmac
import io
import json
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from conftest import headers
from fastapi.testclient import TestClient
from komsu.app import create_app
from komsu.cli import provision
from komsu.config import ChannelConnectorSettings, Settings
from komsu.db import make_engine
from komsu.models import AudioAsset, Base, InboundDelivery, Job, Report
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

SECRET = "contract-test-secret-that-is-at-least-32-bytes"


def connector(name, tenant, actor, source, quota=20):
    return ChannelConnectorSettings(
        connector_id=name,
        tenant_id=tenant,
        actor_id=actor,
        source=source,
        secret=SECRET,
        requests_per_minute=quota,
    )


@pytest.fixture
def channel_setup(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'channels.db'}")
    Base.metadata.create_all(engine)
    admin = provision(engine, "Tenant A")
    other = provision(engine, "Tenant B")
    settings = Settings(
        environment="test",
        requests_per_minute=10_000,
        audio_master_key_b64=base64.b64encode(b"a" * 32).decode(),
        channel_connectors=[
            connector("sms-test", admin["tenant_id"], admin["user_id"], "sms", 2),
            connector("message-test", admin["tenant_id"], admin["user_id"], "messaging"),
            connector("social-test", admin["tenant_id"], admin["user_id"], "social"),
            connector("phone-test", admin["tenant_id"], admin["user_id"], "phone"),
            connector("broken-actor", admin["tenant_id"], other["user_id"], "sms"),
        ],
        _env_file=None,
    )
    with TestClient(create_app(settings, engine)) as client:
        yield engine, client, admin, other
    engine.dispose()


def envelope(**changes):
    return {
        "delivery_id": "delivery-1",
        "external_id": "provider-message-1",
        "text": "Synthetic contract fixture: water needed at test site 12",
        "received_at": datetime.now(UTC).isoformat(),
        "language": "en",
        **changes,
    }


def signed_post(client, connector_id, value, *, timestamp=None, secret=SECRET):
    body = value if isinstance(value, bytes) else json.dumps(value, separators=(",", ":")).encode()
    timestamp = int(time.time()) if timestamp is None else timestamp
    signature = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        f"/api/v1/inbound/{connector_id}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Komsu-Timestamp": str(timestamp),
            "X-Komsu-Signature": signature,
        },
    )


@pytest.mark.parametrize(
    ("connector_id", "source"),
    [("sms-test", "sms"), ("message-test", "messaging"), ("social-test", "social")],
)
def test_text_channel_contract_and_tenant_boundary(channel_setup, connector_id, source):
    engine, client, admin, other = channel_setup
    accepted = signed_post(client, connector_id, envelope())
    assert accepted.status_code == 202, accepted.text
    report_id = accepted.json()["report_id"]
    assert client.get(f"/api/v1/reports/{report_id}", headers=headers(other)).status_code == 404
    detail = client.get(f"/api/v1/reports/{report_id}", headers=headers(admin)).json()
    assert detail["source"] == source and "Synthetic contract fixture" in detail["original_text"]
    with Session(engine) as session:
        receipt = session.scalar(select(InboundDelivery))
        assert receipt.state == "ACCEPTED" and receipt.report_id == report_id
        assert "provider-message-1" not in str(receipt.__dict__)


def test_signature_timestamp_replay_external_id_and_quota(channel_setup):
    engine, client, *_ = channel_setup
    value = envelope()
    first = signed_post(client, "sms-test", value)
    assert first.status_code == 202
    exact = signed_post(client, "sms-test", value)
    assert exact.status_code == 200 and exact.json()["delivery_replayed"]
    provider_duplicate = signed_post(client, "sms-test", {**value, "delivery_id": "delivery-2"})
    assert provider_duplicate.status_code == 202
    assert provider_duplicate.json()["replayed"]
    assert provider_duplicate.json()["report_id"] == first.json()["report_id"]
    assert (
        signed_post(client, "sms-test", {**value, "delivery_id": "delivery-3"}).status_code == 429
    )
    assert signed_post(client, "sms-test", value, secret="x" * 40).status_code == 401
    assert (
        signed_post(client, "sms-test", value, timestamp=int(time.time()) - 301).status_code == 401
    )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 1
        assert session.scalar(select(func.count()).select_from(InboundDelivery)) == 2


def test_malformed_and_conflicting_delivery_dead_letter(channel_setup):
    engine, client, *_ = channel_setup
    malformed = signed_post(client, "message-test", b'{"delivery_id":"bad-1"}')
    assert malformed.status_code == 422
    assert "MALFORMED_PAYLOAD" in malformed.text
    assert signed_post(client, "message-test", b'{"delivery_id":"bad-1"}').status_code == 422
    good = signed_post(client, "social-test", envelope())
    assert good.status_code == 202
    conflict = signed_post(client, "social-test", envelope(text="Different signed body"))
    assert conflict.status_code == 409
    with Session(engine) as session:
        dead = session.scalars(
            select(InboundDelivery).where(InboundDelivery.state == "DEAD_LETTER")
        ).all()
        assert len(dead) == 1 and dead[0].error_code == "MALFORMED_PAYLOAD"
        assert dead[0].report_id is None


def phone_wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        frames = b"".join(
            int(9000 if index % 16 < 8 else -9000).to_bytes(2, "little", signed=True)
            for index in range(16_000)
        )
        output.writeframes(frames)
    return stream.getvalue()


def test_phone_audio_enters_encrypted_quarantine(channel_setup):
    engine, client, *_ = channel_setup
    value = envelope(audio_wav_base64=base64.b64encode(phone_wav()).decode())
    response = signed_post(client, "phone-test", value)
    assert response.status_code == 202, response.text
    with Session(engine) as session:
        asset = session.scalar(select(AudioAsset))
        assert asset.state == "QUARANTINED" and asset.ciphertext != phone_wav()
        assert session.scalar(select(Report.source)) == "phone"


def test_misconfigured_actor_and_retryable_queue_outage(channel_setup):
    engine, client, *_ = channel_setup
    assert signed_post(client, "broken-actor", envelope()).status_code == 503
    first = signed_post(client, "message-test", envelope())
    assert first.status_code == 202
    client.app.state.settings.queue_limit = 1
    second_value = envelope(delivery_id="delivery-2", external_id="provider-message-2")
    unavailable = signed_post(client, "message-test", second_value)
    assert unavailable.status_code == 503 and unavailable.headers["retry-after"] == "30"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(InboundDelivery)) == 1
        session.execute(update(Job).values(state="DONE"))
        session.commit()
    retried = signed_post(client, "message-test", second_value)
    assert retried.status_code == 202


def test_concurrent_quota_is_durable(channel_setup):
    engine, client, *_ = channel_setup
    values = [envelope(delivery_id=f"parallel-{i}", external_id=f"message-{i}") for i in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda value: signed_post(client, "sms-test", value), values))
    assert sorted(response.status_code for response in responses) == [202, 202, 429, 429, 429, 429]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 2
        assert session.scalar(select(func.count()).select_from(InboundDelivery)) == 2


def test_concurrent_conflicting_delivery_creates_one_report(channel_setup):
    engine, client, *_ = channel_setup
    values = [envelope(external_id=f"conflicting-{i}") for i in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda value: signed_post(client, "message-test", value), values))
    assert sorted(response.status_code for response in responses) == [202, 409, 409, 409]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 1


def test_receipt_failure_rolls_back_report_and_audio(channel_setup, monkeypatch):
    engine, client, *_ = channel_setup
    import komsu.app as app_module

    original = app_module.record_delivery

    def fail_receipt(*args, **kwargs):
        raise RuntimeError("Synthetic crash before receipt commit")

    monkeypatch.setattr(app_module, "record_delivery", fail_receipt)
    value = envelope(audio_wav_base64=base64.b64encode(phone_wav()).decode())
    with pytest.raises(RuntimeError, match="Synthetic crash"):
        signed_post(client, "phone-test", value)
    with Session(engine) as session:
        for model in (Report, Job, AudioAsset, InboundDelivery):
            assert session.scalar(select(func.count()).select_from(model)) == 0
    monkeypatch.setattr(app_module, "record_delivery", original)
    assert signed_post(client, "phone-test", value).status_code == 202


def test_local_contract_simulator_and_outage(channel_setup):
    import httpx

    from scripts.inbound_contract_server import create_app as simulator

    _, api, *_ = channel_setup

    def forward(request):
        return httpx.Response(
            api.post(request.url.path, content=request.content, headers=request.headers).status_code
        )

    with TestClient(
        simulator(connector="message-test", secret=SECRET, transport=httpx.MockTransport(forward))
    ) as client:
        assert client.post("/deliver/en").json()["upstream_status"] == 202
        assert client.post("/deliver/en").json()["upstream_status"] == 200

    def unavailable(request):
        raise httpx.ConnectError("Synthetic outage")

    with TestClient(
        simulator(
            connector="message-test", secret=SECRET, transport=httpx.MockTransport(unavailable)
        )
    ) as client:
        assert client.post("/deliver/tr").status_code == 503
    with pytest.raises(ValueError, match="local API"):
        simulator(target="https://example.com", connector="message-test", secret=SECRET)
