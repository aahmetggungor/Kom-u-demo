from concurrent.futures import ThreadPoolExecutor

from conftest import headers
from komsu.models import Audit, Report
from komsu.worker import process_one
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_workflow import payload, receive


def prepared(setup):
    engine, client, admin, *_ = setup
    messages = [
        payload(text="Synthetic earthquake: water"),
        payload(text="Synthetic earthquake: injured"),
    ]
    accepted = [receive(setup, message) for message in messages]
    while process_one(engine, admin["tenant_id"]):
        pass
    cases = [
        client.get(f"/api/v1/cases/{r['case_id']}", headers=headers(admin)).json() for r in accepted
    ]
    return accepted, messages, cases


def merge_body(cases):
    return {
        "target_case_id": cases[1]["id"],
        "expected_source_version": cases[0]["version"],
        "expected_target_version": cases[1]["version"],
        "reason": "Synthetic human grouping review",
    }


def test_merge_split_preserves_reports_and_requires_new_review(setup):
    engine, client, admin, *_ = setup
    accepted, messages, cases = prepared(setup)
    verified = client.post(
        f"/api/v1/cases/{cases[1]['id']}/review",
        headers=headers(admin),
        json={
            "expected_version": cases[1]["version"],
            "verification_status": "VERIFIED",
            "urgency_level": "HIGH",
            "location": {"lat": 38.4, "lon": 27.1},
            "confirm_location": True,
            "region": "Synthetic region",
            "reason": "Synthetic prior verification",
        },
    )
    assert verified.status_code == 200
    cases[1] = verified.json()
    response = client.post(
        f"/api/v1/cases/{cases[0]['id']}/merge", headers=headers(admin), json=merge_body(cases)
    )
    assert response.status_code == 200, response.text
    target = response.json()
    assert target["report_count"] == 2 and target["human_review_required"]
    assert target["verification_status"] == "UNVERIFIED" and target["location"]["lat"] is None
    assert target["region"] is None and target["urgency_level"] == "UNKNOWN"
    assert receive(setup, messages[0])["case_id"] == target["id"]
    source = client.get(f"/api/v1/cases/{cases[0]['id']}", headers=headers(admin)).json()
    assert source["status"] == "MERGED" and source["merged_into_id"] == target["id"]
    assert client.get("/api/v1/cases", headers=headers(admin)).json()["total"] == 1
    split = client.post(
        f"/api/v1/cases/{target['id']}/split",
        headers=headers(admin),
        json={
            "expected_version": target["version"],
            "report_ids": [accepted[0]["report_id"]],
            "reason": "Synthetic correction after review",
        },
    )
    assert split.status_code == 200, split.text
    assert split.json()["report_count"] == 1 and split.json()["human_review_required"]
    assert client.get("/api/v1/cases", headers=headers(admin)).json()["total"] == 2
    with Session(engine) as session:
        originals = session.scalars(select(Report.original_text)).all()
        assert sorted(originals) == sorted(m["text"] for m in messages)
        logs = session.scalars(select(Audit)).all()
        assert all("Synthetic human grouping review" not in str(row.detail) for row in logs)


def test_merge_race_and_role_scope(setup):
    _, client, admin, other, observer, _ = setup
    _, _, cases = prepared(setup)
    path = f"/api/v1/cases/{cases[0]['id']}/merge"
    body = merge_body(cases)
    assert client.post(path, headers=headers(observer), json=body).status_code == 403
    assert client.post(path, headers=headers(other), json=body).status_code == 404
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: client.post(path, headers=headers(admin), json=body).status_code, range(2)
            )
        )
    assert sorted(results) == [200, 409]


def test_pending_analysis_and_invalid_split_rejected(setup):
    _, client, admin, *_ = setup
    first, second = receive(setup), receive(setup)
    response = client.post(
        f"/api/v1/cases/{first['case_id']}/merge",
        headers=headers(admin),
        json={
            "target_case_id": second["case_id"],
            "expected_source_version": 1,
            "expected_target_version": 1,
            "reason": "Synthetic check",
        },
    )
    assert response.status_code == 409
    _, _, cases = prepared(setup)
    response = client.post(
        f"/api/v1/cases/{cases[0]['id']}/split",
        headers=headers(admin),
        json={
            "expected_version": cases[0]["version"],
            "report_ids": [cases[0]["reports"][0]["id"]],
            "reason": "Synthetic check",
        },
    )
    assert response.status_code == 422
