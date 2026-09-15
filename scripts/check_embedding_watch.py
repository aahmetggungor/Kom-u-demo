"""Local integration check using actual model, synthetic tenant and two arrivals."""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

from dotenv import load_dotenv
from komsu.cli import provision
from komsu.db import make_engine, tenant_session
from komsu.domain import ingest
from komsu.schemas import ReportIn
from komsu.security import Principal
from sqlalchemy import text

load_dotenv()
admin = make_engine(os.environ["KOMSU_ADMIN_DATABASE_URL"])
runtime = make_engine(os.environ["KOMSU_DATABASE_URL"])
identity = provision(admin, "Synthetic embedding watch integration")
tenant = identity["tenant_id"]
actor = Principal(tenant, identity["user_id"], identity["role"])


def arrive(message, language):
    with tenant_session(runtime, tenant) as session:
        ingest(
            session,
            actor,
            ReportIn.model_validate(
                {
                    "client_id": str(uuid4()),
                    "text": message,
                    "language": language,
                    "occurred_at": datetime.now(UTC).isoformat(),
                }
            ),
            10000,
        )


def wait_for_count(expected, timeout):
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if worker.poll() is not None:
            raise RuntimeError("Embedding worker exited unexpectedly")
        with tenant_session(runtime, tenant) as session:
            count = session.scalar(
                text("SELECT count(*) FROM report_embeddings WHERE tenant_id=:tenant"),
                {"tenant": tenant},
            )
        if count == expected:
            return round(time.monotonic() - started, 3)
        time.sleep(1)
    raise TimeoutError("Expected embeddings were not committed")


arrive("SYNTHETIC: We need drinking water at the training shelter.", "en")
worker = subprocess.Popen(
    [
        sys.executable,
        "scripts/embed_reports.py",
        "--tenant",
        tenant,
        "--watch",
        "--poll-seconds",
        "1",
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
)
try:
    first = wait_for_count(1, 90)
    arrive("SYNTHETIC: Eğitim barınağında içme suyuna ihtiyacımız var.", "tr")
    second = wait_for_count(2, 30)
    print(
        json.dumps(
            {
                "actual_local_model": True,
                "first_arrival_seconds": first,
                "second_arrival_seconds": second,
                "committed_embeddings": 2,
            }
        )
    )
finally:
    worker.terminate()
    worker.wait(timeout=10)
    runtime.dispose()
    admin.dispose()
