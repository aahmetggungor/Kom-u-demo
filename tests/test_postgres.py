import base64
import hashlib
import hmac
import io
import json
import math
import os
import struct
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from conftest import headers
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from komsu.app import create_app
from komsu.cli import provision
from komsu.config import ChannelConnectorSettings, Settings
from komsu.db import make_engine, tenant_session
from komsu.models import AudioAsset, AudioTranscript, Audit, Case, InboundDelivery
from komsu.worker import process_one
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres


def test_postgres_inbound_concurrent_quota_and_atomic_retry(pg, monkeypatch):
    import komsu.app as app_module
    from komsu.config import ChannelConnectorSettings
    from komsu.models import InboundDelivery, Report
    from sqlalchemy import func
    from test_inbound_channels import SECRET, envelope, signed_post

    engine, _, actor, _ = pg
    settings = Settings(
        environment="test",
        requests_per_minute=10000,
        _env_file=None,
        channel_connectors=[
            ChannelConnectorSettings(
                connector_id="pg-race",
                tenant_id=actor["tenant_id"],
                actor_id=actor["user_id"],
                source="sms",
                secret=SECRET,
                requests_per_minute=2,
            )
        ],
    )
    with TestClient(create_app(settings, engine)) as client:
        value = envelope()
        original = app_module.record_delivery

        def fail(*args, **kwargs):
            raise RuntimeError("Synthetic receipt crash")

        monkeypatch.setattr(app_module, "record_delivery", fail)
        with pytest.raises(RuntimeError, match="Synthetic receipt"):
            signed_post(client, "pg-race", value)
        with tenant_session(engine, actor["tenant_id"]) as session:
            assert session.scalar(select(func.count()).select_from(Report)) == 0
        monkeypatch.setattr(app_module, "record_delivery", original)
        values = [
            envelope(delivery_id=f"parallel-{i}", external_id=f"external-{i}") for i in range(6)
        ]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda value: signed_post(client, "pg-race", value), values))
        assert sorted(result.status_code for result in results) == [202, 202, 429, 429, 429, 429]
        with tenant_session(engine, actor["tenant_id"]) as session:
            assert session.scalar(select(func.count()).select_from(Report)) == 2
            assert session.scalar(select(func.count()).select_from(InboundDelivery)) == 2


AUDIO_KEY = base64.b64encode(b"P" * 32).decode()


def audio_fixture():
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(
            b"".join(
                struct.pack("<h", round(7000 * math.sin(2 * math.pi * 440 * i / 16_000)))
                for i in range(4000)
            )
        )
    return output.getvalue()


def test_retention_requires_second_admin_and_purges_derivatives(pg):
    from komsu.retention import execute
    from komsu.semantic import store_embedding

    engine, client, actor, other = pg
    admin_engine = make_engine(os.environ["KOMSU_ADMIN_DATABASE_URL"])
    approver = provision(admin_engine, "Synthetic retention approver", "admin", actor["tenant_id"])
    report, _ = pg_report(pg)
    while process_one(engine, actor["tenant_id"]):
        pass
    detail = client.get(f"/api/v1/cases/{report['case_id']}", headers=headers(actor)).json()
    response = client.post(
        f"/api/v1/cases/{report['case_id']}/review",
        headers=headers(actor),
        json={
            "expected_version": detail["version"],
            "verification_status": "VERIFIED",
            "urgency_level": "HIGH",
            "location": {"lat": 38.4, "lon": 27.1},
            "confirm_location": True,
            "reason": "Synthetic reason to redact",
        },
    )
    assert response.status_code == 200, response.text
    with tenant_session(engine, actor["tenant_id"]) as session:
        store_embedding(
            session, actor["tenant_id"], report["report_id"], "retention-test", [1.0] + [0.0] * 1023
        )
        session.commit()
    with TestClient(
        create_app(
            Settings(
                environment="test",
                requests_per_minute=10000,
                audio_master_key_b64=AUDIO_KEY,
                _env_file=None,
            ),
            engine,
        )
    ) as audio_api:
        uploaded = audio_api.post(
            f"/api/v1/reports/{report['report_id']}/audio",
            headers={**headers(actor), "Content-Type": "audio/wav"},
            content=audio_fixture(),
        )
        assert uploaded.status_code == 201, uploaded.text
    with tenant_session(engine, other["tenant_id"]) as session:
        assert (
            session.scalar(select(AudioAsset).where(AudioAsset.report_id == report["report_id"]))
            is None
        )
    payload = {
        "cutoff_at": datetime.now(UTC).isoformat(),
        "execute_after": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "reason_code": "INCIDENT_ENDED",
    }
    scheduled = client.post("/api/v1/retention/plans", headers=headers(actor), json=payload)
    assert scheduled.status_code == 201, scheduled.text
    assert scheduled.json()["preview_audio_count"] == 1
    plan_id = scheduled.json()["id"]
    approval = {"expected_status": "SCHEDULED", "acknowledge_irreversible_purge": True}
    assert (
        client.post(
            f"/api/v1/retention/plans/{plan_id}/approve", headers=headers(actor), json=approval
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/retention/plans/{plan_id}/approve", headers=headers(approver), json=approval
        ).status_code
        == 200
    )
    hold = client.post(
        "/api/v1/retention/holds",
        headers=headers(actor),
        json={
            "reason_code": "SECURITY_INVESTIGATION",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert hold.status_code == 201 and hold.json()["active"] is True
    with Session(admin_engine) as session:
        session.execute(
            text("UPDATE retention_plans SET execute_after=cutoff_at WHERE id=:id"),
            {"id": plan_id},
        )
        session.commit()
    with pytest.raises(ValueError):
        execute(admin_engine, plan_id, "wrong-confirmation")
    with pytest.raises(ValueError, match="legal hold"):
        execute(admin_engine, plan_id, plan_id)
    released = client.post(
        f"/api/v1/retention/holds/{hold.json()['id']}/release",
        headers=headers(actor),
        json={"expected_active": True, "reason_code": "HOLD_ENDED"},
    )
    assert released.status_code == 200 and released.json()["active"] is False
    counts = execute(admin_engine, plan_id, plan_id)
    assert counts["reports_redacted"] == 1 and counts["embeddings_deleted"] == 1
    assert counts["audio_assets_deleted"] == 1
    with Session(admin_engine) as session:
        row = session.execute(
            text(
                "SELECT original_text,address_raw,reported_lat,analysis FROM reports WHERE id=:id"
            ),
            {"id": report["report_id"]},
        ).one()
        assert row.original_text == "[PURGED_AFTER_RETENTION]" and row.address_raw is None
        assert row.reported_lat is None and row.analysis == {"retention": "PURGED"}
        assert (
            session.scalar(
                text("SELECT count(*) FROM audio_assets WHERE report_id=:id"),
                {"id": report["report_id"]},
            )
            == 0
        )
        assert (
            session.scalar(
                text("SELECT count(*) FROM case_locations WHERE case_id=:id"),
                {"id": report["case_id"]},
            )
            == 0
        )
        assert (
            session.scalar(
                text("SELECT reason FROM review_history WHERE case_id=:id"),
                {"id": report["case_id"]},
            )
            == "[PURGED_AFTER_RETENTION]"
        )
    foreign, _ = pg_report((engine, client, other, actor))
    assert (
        client.get(f"/api/v1/reports/{foreign['report_id']}", headers=headers(other))
        .json()["original_text"]
        .startswith("Earthquake")
    )
    replacement = client.post("/api/v1/retention/plans", headers=headers(actor), json=payload)
    assert replacement.status_code == 201
    cancelled = client.post(
        f"/api/v1/retention/plans/{replacement.json()['id']}/cancel",
        headers=headers(actor),
        json={"expected_status": "SCHEDULED", "reason_code": "INCIDENT_REOPENED"},
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    admin_engine.dispose()


def test_embedding_batch_recovers_after_invalid_model_output(pg):
    from komsu.embedding_worker import embed_batch, pending_reports
    from komsu.worker_observability import EmbeddingMetrics
    from prometheus_client import generate_latest

    engine, _, actor, _ = pg
    for _ in range(5):
        pg_report(pg)
    tenant = actor["tenant_id"]
    revision = "recovery-test"

    class Model:
        calls = 0

        def encode(self, texts):
            self.calls += 1
            if self.calls == 2:
                return [[float("nan")] * 1024 for _ in texts]
            return [[1.0] + [0.0] * 1023 for _ in texts]

    rows = pending_reports(engine, tenant, revision)
    metrics = EmbeddingMetrics()
    with pytest.raises(ValueError):
        embed_batch(engine, tenant, revision, Model(), rows, metrics=metrics)
    output = generate_latest(metrics.registry).decode()
    assert "komsu_embedding_reports_total 4.0" in output
    assert 'komsu_embedding_batches_total{result="model_error"} 1.0' in output
    remaining = pending_reports(engine, tenant, revision)
    assert len(remaining) == 1  # First committed sub-batch survives failure.
    assert embed_batch(engine, tenant, revision, Model(), remaining, metrics=metrics) == 1
    assert embed_batch(engine, tenant, revision, Model(), remaining, metrics=metrics) == 0
    assert "komsu_embedding_reports_total 5.0" in generate_latest(metrics.registry).decode()
    assert pending_reports(engine, tenant, revision) == []
    with tenant_session(engine, tenant) as session:
        assert (
            session.scalar(
                text("SELECT count(*) FROM reports WHERE tenant_id=:tenant"), {"tenant": tenant}
            )
            == 5
        )


def test_semantic_revision_tenant_and_time_isolation(pg):
    from komsu.semantic import similar_cases, store_embedding

    engine, client, actor, other = pg
    source, _ = pg_report(pg)
    near, _ = pg_report(pg)
    stale, _ = pg_report(pg)
    foreign, _ = pg_report((engine, client, other, actor))
    basis = [1.0] + [0.0] * 1023
    with tenant_session(engine, actor["tenant_id"]) as session:
        for report in (source, near, stale):
            store_embedding(session, actor["tenant_id"], report["report_id"], "test-v1", basis)
        session.execute(
            text("UPDATE reports SET occurred_at=occurred_at-interval '48 hours' WHERE id=:id"),
            {"id": stale["report_id"]},
        )
        session.commit()
    with tenant_session(engine, other["tenant_id"]) as session:
        store_embedding(session, other["tenant_id"], foreign["report_id"], "test-v1", basis)
        session.commit()
    with tenant_session(engine, actor["tenant_id"]) as session:
        result = similar_cases(session, actor["tenant_id"], source["case_id"], "test-v1")
        assert [item["case_id"] for item in result] == [near["case_id"]]
        assert result[0]["semantic_similarity"] == pytest.approx(1)
        assert result[0]["distance_m"] == pytest.approx(0)
        assert result[0]["human_review_required"] is True
        assert set(result[0]["signals"]) == {"semantic", "location", "time", "address", "needs"}
        assert result[0]["location_basis"] == "REPORTED_OR_MIXED"
        assert result[0]["recommendation"] in {
            "REVIEW_CANDIDATE",
            "INSUFFICIENT_OR_CONFLICTING_EVIDENCE",
        }
        assert similar_cases(session, actor["tenant_id"], source["case_id"], "test-v2") == []
    with TestClient(create_app(Settings(embedding_revision="test-v1"), engine)) as enabled:
        response = enabled.get(f"/api/v1/cases/{source['case_id']}/similar", headers=headers(actor))
        assert response.status_code == 200
        assert response.json()["items"][0]["case_id"] == near["case_id"]
        assert (
            enabled.get(
                f"/api/v1/cases/{foreign['case_id']}/similar", headers=headers(actor)
            ).status_code
            == 404
        )


def test_postgres_human_merge_and_split(pg):
    engine, client, actor, _ = pg
    first, _ = pg_report(pg)
    second, _ = pg_report(pg)
    while process_one(engine, actor["tenant_id"]):
        pass
    cases = [
        client.get(f"/api/v1/cases/{r['case_id']}", headers=headers(actor)).json()
        for r in (first, second)
    ]
    body = {
        "target_case_id": cases[1]["id"],
        "expected_source_version": cases[0]["version"],
        "expected_target_version": cases[1]["version"],
        "reason": "Synthetic PostgreSQL merge",
    }
    path = f"/api/v1/cases/{cases[0]['id']}/merge"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post(path, headers=headers(actor), json=body), range(2))
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    target = next(r.json() for r in responses if r.status_code == 200)
    assert target["report_count"] == 2 and target["location"]["lat"] is None
    response = client.post(
        f"/api/v1/cases/{target['id']}/split",
        headers=headers(actor),
        json={
            "expected_version": target["version"],
            "report_ids": [first["report_id"]],
            "reason": "Synthetic PostgreSQL split",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["report_count"] == 1


@pytest.fixture
def pg():
    if os.environ.get("KOMSU_RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Set KOMSU_RUN_POSTGRES_TESTS=1 for local dedicated PostgreSQL")
    load_dotenv()
    admin_engine = make_engine(os.environ["KOMSU_ADMIN_DATABASE_URL"])
    runtime = make_engine(os.environ["KOMSU_DATABASE_URL"])
    a = provision(admin_engine, "Synthetic PostgreSQL test A")
    b = provision(admin_engine, "Synthetic PostgreSQL test B")
    with TestClient(create_app(Settings(requests_per_minute=10000), runtime)) as client:
        yield runtime, client, a, b
    runtime.dispose()
    admin_engine.dispose()


def pg_report(pg):
    _, client, a, _ = pg
    data = {
        "client_id": str(uuid4()),
        "text": "Earthquake: people trapped, medical help",
        "language": "en",
        "occurred_at": datetime.now(UTC).isoformat(),
        "location": {"lat": 38.4, "lon": 27.1},
    }
    result = client.post("/api/v1/reports", headers=headers(a), json=data)
    assert result.status_code == 202, result.text
    return result.json(), data


def test_postgres_rls_auth_and_fail_closed(pg):
    engine, client, a, b = pg
    item, _ = pg_report(pg)
    assert client.get("/health/ready").status_code == 200
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM cases")).scalar() == 0
        assert (
            connection.execute(
                text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
            ).scalar()
            is False
        )
    with tenant_session(engine, b["tenant_id"]) as session:
        assert session.scalar(select(Case).where(Case.id == item["case_id"])) is None
    with tenant_session(engine, a["tenant_id"]) as session:
        assert session.scalar(select(Case).where(Case.id == item["case_id"])) is not None
    assert client.get(f"/api/v1/cases/{item['case_id']}", headers=headers(b)).status_code == 404


def test_postgres_inbound_connector_actor_and_receipt_rls(pg):
    engine, _, actor, other = pg
    secret = "postgres-contract-secret-that-is-at-least-32-bytes"
    settings = Settings(
        requests_per_minute=10_000,
        channel_connectors=[
            ChannelConnectorSettings(
                connector_id="postgres-sms",
                tenant_id=actor["tenant_id"],
                actor_id=actor["user_id"],
                source="sms",
                secret=secret,
            )
        ],
    )
    value = {
        "delivery_id": str(uuid4()),
        "external_id": str(uuid4()),
        "text": "Synthetic PostgreSQL inbound contract",
        "received_at": datetime.now(UTC).isoformat(),
        "language": "en",
    }
    body = json.dumps(value, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    with TestClient(create_app(settings, engine)) as inbound_api:
        response = inbound_api.post(
            "/api/v1/inbound/postgres-sms",
            content=body,
            headers={"X-Komsu-Timestamp": str(timestamp), "X-Komsu-Signature": signature},
        )
    assert response.status_code == 202, response.text
    with tenant_session(engine, actor["tenant_id"]) as session:
        assert session.scalar(select(InboundDelivery.report_id)) == response.json()["report_id"]
    with tenant_session(engine, other["tenant_id"]) as session:
        assert session.scalar(select(InboundDelivery)) is None
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM inbound_deliveries")).scalar() == 0


def test_postgres_audio_scan_release_is_tenant_scoped_and_race_safe(pg):
    from komsu.ai import TranscriptionOutput
    from komsu.audio_scanning import ScanOutcome, ScanVerdict, scan_audio_asset
    from komsu.transcription_worker import process_one_transcription

    engine, client, uploader, other = pg
    item, _ = pg_report(pg)
    uploaded = client.post(
        f"/api/v1/reports/{item['report_id']}/audio",
        headers={**headers(uploader), "Content-Type": "audio/wav"},
        content=audio_fixture(),
    )
    assert uploaded.status_code == 201, uploaded.text

    class Scanner:
        def scan(self, payload):
            assert payload.startswith(b"RIFF")
            return ScanOutcome(ScanVerdict.CLEAN, "NO_THREAT_DETECTED")

    settings = Settings()
    with tenant_session(engine, uploader["tenant_id"]) as session:
        scanned, _ = scan_audio_asset(
            session,
            uploader["tenant_id"],
            uploaded.json()["id"],
            Scanner(),
            "postgres-test-scanner-v1",
            settings.audio_master_key_b64,
        )
        assert scanned.state == "SCAN_PASSED" and scanned.version == 2
    assert (
        client.post(
            f"/api/v1/reports/{item['report_id']}/audio/decision",
            headers=headers(other),
            json={"expected_version": 2, "decision": "RELEASE", "reason": "foreign tenant"},
        ).status_code
        == 404
    )

    admin_engine = make_engine(os.environ["KOMSU_ADMIN_DATABASE_URL"])
    first = provision(admin_engine, "Audio approver one", "coordinator", uploader["tenant_id"])
    second = provision(admin_engine, "Audio approver two", "coordinator", uploader["tenant_id"])
    admin_engine.dispose()
    path = f"/api/v1/reports/{item['report_id']}/audio/decision"

    def release(identity):
        return client.post(
            path,
            headers=headers(identity),
            json={
                "expected_version": 2,
                "decision": "RELEASE",
                "reason": f"Reviewed by {identity['user_id']}",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(release, [first, second])) == [200, 409]
    detail = client.get(f"/api/v1/reports/{item['report_id']}", headers=headers(uploader)).json()
    assert detail["audio"]["state"] == "RELEASED"
    assert detail["audio"]["scan_verdict"] == "CLEAN"
    assert "ciphertext" not in detail["audio"]

    class Transcriber:
        def transcribe_bytes(self, payload, language_hint=None):
            assert payload.startswith(b"RIFF")
            return TranscriptionOutput(
                "Synthetic PostgreSQL transcript",
                language_hint or "und",
                "postgres-fake-whisper-v1",
                0.25,
                (),
            )

    assert process_one_transcription(
        engine,
        uploader["tenant_id"],
        Transcriber(),
        settings.audio_master_key_b64,
    )
    detail = client.get(f"/api/v1/reports/{item['report_id']}", headers=headers(uploader)).json()
    assert detail["transcript"]["state"] == "DONE"
    assert detail["transcript"]["original_text"] == "Synthetic PostgreSQL transcript"
    assert "CONFIDENCE_UNAVAILABLE" in detail["transcript"]["warnings"]
    with tenant_session(engine, other["tenant_id"]) as session:
        assert (
            session.scalar(
                select(AudioTranscript).where(AudioTranscript.report_id == item["report_id"])
            )
            is None
        )


def test_postgres_ingestion_concurrency_and_worker(pg):
    engine, client, a, _ = pg
    item, data = pg_report(pg)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda _: client.post("/api/v1/reports", headers=headers(a), json=data), range(4)
            )
        )
    assert all(r.status_code == 202 and r.json()["report_id"] == item["report_id"] for r in results)
    assert process_one(engine, a["tenant_id"])
    result = client.get(f"/api/v1/cases/{item['case_id']}", headers=headers(a)).json()
    assert result["urgency_level"] == "CRITICAL" and result["location_status"] == "UNCONFIRMED"


def test_postgis_vector_and_human_dispatch_race(pg):
    engine, client, a, _ = pg
    item, _ = pg_report(pg)
    route = f"/api/v1/cases/{item['case_id']}"
    body = {
        "expected_version": 1,
        "verification_status": "VERIFIED",
        "urgency_level": "CRITICAL",
        "location": {"lat": 38.4, "lon": 27.1},
        "confirm_location": True,
        "reason": "Synthetic telephone confirmation",
    }
    reviewed = client.post(route + "/review", headers=headers(a), json=body)
    assert reviewed.status_code == 200, reviewed.text
    with tenant_session(engine, a["tenant_id"]) as session:
        distance = session.execute(
            text(
                "SELECT ST_Distance(position, ST_SetSRID(ST_MakePoint(27.1,38.4),4326)::geography) FROM case_locations WHERE case_id=:id"
            ),
            {"id": item["case_id"]},
        ).scalar()
        assert distance == 0
        assert session.execute(text("SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector")).scalar() == 0
    team = client.get("/api/v1/teams", headers=headers(a)).json()[0]["id"]
    request = {"expected_version": 2, "team_id": team}
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(
            executor.map(
                lambda _: (
                    client.post(route + "/dispatch", headers=headers(a), json=request).status_code
                ),
                range(2),
            )
        )
    assert sorted(codes) == [200, 409]


def test_postgres_audit_append_only_and_cross_tenant_write(pg):
    engine, _, a, b = pg
    item, _ = pg_report(pg)
    with tenant_session(engine, a["tenant_id"]) as session:
        entry = session.scalar(select(Audit).where(Audit.target_id == item["report_id"]))
        assert entry
        with pytest.raises(DBAPIError):
            session.execute(text("DELETE FROM audit_log WHERE id=:id"), {"id": entry.id})
        session.rollback()
        with pytest.raises(DBAPIError):
            session.execute(
                text("UPDATE cases SET tenant_id=:other WHERE id=:id"),
                {"other": b["tenant_id"], "id": item["case_id"]},
            )
        session.rollback()
