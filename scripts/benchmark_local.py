"""Bounded synthetic HTTP burst then queue drain; never an operational capacity claim."""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from komsu.cli import provision
from komsu.db import make_engine, tenant_session
from komsu.models import Case, Report
from komsu.pipeline import Pipeline
from komsu.worker import process_one
from sqlalchemy import select


def percentiles(values):
    ordered = sorted(values)
    return {
        name: round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * q))], 3)
        for name, q in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, choices=range(1, 61), default=30)
    args = parser.parse_args()
    load_dotenv()
    admin = make_engine(os.environ["KOMSU_ADMIN_DATABASE_URL"])
    engine = make_engine(os.environ["KOMSU_DATABASE_URL"])
    identity = provision(admin, "Synthetic local benchmark")
    tenant = identity["tenant_id"]
    started = time.perf_counter()
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=15, trust_env=False) as client:

        def submit(index):
            before = time.perf_counter()
            response = client.post(
                "/api/v1/reports",
                headers={"Authorization": "Bearer " + identity["token"]},
                json={
                    "client_id": str(uuid4()),
                    "text": f"Synthetic earthquake test {index}: people trapped, water needed",
                    "language": "en",
                    "occurred_at": datetime.now(UTC).isoformat(),
                },
            )
            response.raise_for_status()
            assert response.status_code == 202
            return (time.perf_counter() - before) * 1000

        with ThreadPoolExecutor(max_workers=6) as pool:
            ingestion = list(pool.map(submit, range(args.samples)))
    pipeline = Pipeline(tenant)
    while process_one(engine, tenant, pipeline):
        pass
    elapsed = time.perf_counter() - started
    with tenant_session(engine, tenant) as session:
        rows = session.execute(
            select(Report.processing_status, Report.created_at, Case.updated_at).join(
                Case, Case.id == Report.case_id
            )
        ).all()
    assert len(rows) == args.samples and all(row[0] == "PROCESSED" for row in rows)
    result = {
        "measured_at": datetime.now(UTC).isoformat(),
        "scenario": "local Docker API/PostgreSQL; 6 HTTP clients burst then one host worker drains queue",
        "samples": args.samples,
        "ingestion_ack_ms": percentiles(ingestion),
        "persist_to_rule_analysis_ms": percentiles(
            [(end - start).total_seconds() * 1000 for _, start, end in rows]
        ),
        "elapsed_seconds": round(elapsed, 3),
        "all_processed": True,
        "limits": "No model inference, external services, human triage, sustained load or failover measured. Queue drain deliberately begins after ingestion burst. Small local sample; not an SLO or capacity guarantee.",
    }
    Path("docs/evaluation/local-benchmark.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    admin.dispose()
    engine.dispose()


if __name__ == "__main__":
    main()
