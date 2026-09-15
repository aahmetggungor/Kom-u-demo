from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from conftest import headers
from komsu.ai import BaselineAnalyzer
from komsu.models import AccessToken, Audit, Case, Dispatch, Job, Report, utcnow
from komsu.worker import process_one
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session


def payload(**changes):
    return {
        "client_id": str(uuid4()),
        "text": "Hatay'da deprem: enkaz altında 3 kişi mahsur",
        "source": "android",
        "language": "tr",
        "occurred_at": datetime.now(UTC).isoformat(),
        **changes,
    }


def receive(setup, data=None):
    _, client, admin, *_ = setup
    response = client.post("/api/v1/reports", headers=headers(admin), json=data or payload())
    assert response.status_code == 202, response.text
    return response.json()


def test_idempotency_cross_transport_and_conflict(setup):
    engine, client, admin, *_ = setup
    data = payload()
    first = receive(setup, data)
    second = receive(setup, {**data, "source": "sms"})
    assert second["replayed"] and second["report_id"] == first["report_id"]
    assert (
        client.post(
            "/api/v1/reports", headers=headers(admin), json={**data, "text": "different"}
        ).status_code
        == 409
    )
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Report)) == 1
        assert s.scalar(select(func.count()).select_from(Job)) == 1


def test_tenant_and_role_boundaries(setup):
    _, client, admin, other, observer, rescue = setup
    item = receive(setup)
    for path in [f"/cases/{item['case_id']}", f"/reports/{item['report_id']}"]:
        assert client.get("/api/v1" + path, headers=headers(other)).status_code == 404
    assert client.get("/api/v1/cases", headers=headers(other)).json()["total"] == 0
    assert client.get("/api/v1/events", headers=headers(other)).json()["items"] == []
    assert (
        client.post("/api/v1/reports", headers=headers(observer), json=payload()).status_code == 403
    )
    assert client.get("/api/v1/cases").status_code == 401
    assert (
        client.post(
            "/api/v1/reports", headers=headers(admin), json=payload(tenant_id=other["tenant_id"])
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/cases/{item['case_id']}/review",
            headers=headers(rescue),
            json=review_payload(),
        ).status_code
        == 403
    )


def review_payload(**changes):
    return {
        "expected_version": 1,
        "verification_status": "VERIFIED",
        "urgency_level": "HIGH",
        "location": {"lat": 36.2, "lon": 36.1},
        "confirm_location": True,
        "reason": "Telephone verification by coordinator",
        **changes,
    }


def test_human_dispatch_version_and_audit(setup):
    engine, client, admin, *_ = setup
    item = receive(setup)
    route = f"/api/v1/cases/{item['case_id']}"
    team = client.get("/api/v1/teams", headers=headers(admin)).json()[0]["id"]
    request = {"expected_version": 1, "team_id": team}
    assert client.post(route + "/dispatch", headers=headers(admin), json=request).status_code == 409
    reviewed = client.post(route + "/review", headers=headers(admin), json=review_payload())
    assert reviewed.status_code == 200, reviewed.text
    assert (
        client.post(route + "/review", headers=headers(admin), json=review_payload()).status_code
        == 409
    )
    result = client.post(
        route + "/dispatch", headers=headers(admin), json={**request, "expected_version": 2}
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "DISPATCHED"
    assert (
        client.post(
            route + "/dispatch", headers=headers(admin), json={**request, "expected_version": 2}
        ).status_code
        == 409
    )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Dispatch)) == 1
        actions = session.scalars(select(Audit.action)).all()
        assert "case.dispatched" in actions and "case.reviewed" in actions


def test_worker_does_not_overwrite_human(setup):
    engine, client, admin, *_ = setup
    item = receive(setup)
    route = f"/api/v1/cases/{item['case_id']}"
    assert (
        client.post(
            route + "/review", headers=headers(admin), json=review_payload(urgency_level="LOW")
        ).status_code
        == 200
    )
    assert process_one(engine, admin["tenant_id"])
    detail = client.get(route, headers=headers(admin)).json()
    assert detail["urgency_level"] == "LOW"
    assert detail["location_status"] == "CONFIRMED"
    assert detail["reports"][0]["analysis"]["urgency_level"] == "CRITICAL"
    assert not process_one(engine, admin["tenant_id"])


def test_model_failure_retains_source_and_retries(setup):
    class Broken:
        def analyze(self, *args):
            raise RuntimeError("sensitive source must not leak")

    engine, client, admin, *_ = setup
    original = payload()
    item = receive(setup, original)
    assert process_one(engine, admin["tenant_id"], Broken())
    detail = client.get(f"/api/v1/cases/{item['case_id']}", headers=headers(admin)).json()
    assert detail["reports"][0]["original_text"] == original["text"]
    assert detail["human_review_required"]
    assert "sensitive" not in str(detail)
    with Session(engine) as session:
        job = session.scalar(select(Job))
        assert job.state == "QUEUED" and job.attempts == 1
        job.available_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert process_one(engine, admin["tenant_id"], BaselineAnalyzer())


def test_expired_lease_recovery(setup):
    engine, _, admin, *_ = setup
    receive(setup)
    with Session(engine) as session:
        job = session.scalar(select(Job))
        job.state = "RUNNING"
        job.claim_id = str(uuid4())
        job.lease_until = utcnow() - timedelta(minutes=5)
        session.commit()
    assert process_one(engine, admin["tenant_id"])
    with Session(engine) as session:
        assert session.scalar(select(Job.state)) == "DONE"


def test_validation_and_pii_error_response(setup):
    _, client, admin, *_ = setup
    for data in [
        payload(text="   "),
        payload(location={"lat": 91, "lon": 20}),
        payload(occurred_at="2026-01-01T00:00:00"),
        payload(text="x" * 8001),
        payload(source="unknown"),
    ]:
        result = client.post("/api/v1/reports", headers=headers(admin), json=data)
        assert result.status_code == 422
        assert "input" not in result.text and "original_text" not in result.text
    assert (
        client.post("/api/v1/reports", headers=headers(admin), content=b"x" * 40000).status_code
        == 413
    )


def test_token_revocation(setup):
    engine, client, admin, *_ = setup
    with Session(engine) as session:
        session.execute(
            update(AccessToken).where(AccessToken.user_id == admin["user_id"]).values(revoked=True)
        )
        session.commit()
    assert client.get("/api/v1/auth/me", headers=headers(admin)).status_code == 401


def test_concurrent_ingestion(setup):
    engine, client, admin, *_ = setup
    data = payload()
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post("/api/v1/reports", headers=headers(admin), json=data),
                range(2),
            )
        )
    assert all(r.status_code == 202 for r in responses), [r.text for r in responses]
    assert len({r.json()["case_id"] for r in responses}) == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Case)) == 1


def test_event_replay(setup):
    _, client, admin, *_ = setup
    receive(setup)
    first = client.get("/api/v1/events", headers=headers(admin)).json()["items"]
    receive(setup)
    rest = client.get(f"/api/v1/events?after={first[-1]['id']}", headers=headers(admin)).json()[
        "items"
    ]
    assert len(rest) == 1 and rest[0]["id"] > first[-1]["id"]
