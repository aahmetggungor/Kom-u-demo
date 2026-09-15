"""Explicit bounded local embedding batch; no report text leaves this machine."""

import argparse
import json
import time
from pathlib import Path
from uuid import UUID

from komsu.ai import LocalBgeM3
from komsu.config import Settings
from komsu.db import make_engine
from komsu.embedding_worker import embed_batch, pending_reports
from komsu.worker_observability import EmbeddingMetrics
from sqlalchemy.exc import OperationalError

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tenant", required=True, type=UUID)
parser.add_argument("--limit", type=int, default=100)
parser.add_argument("--watch", action="store_true", help="Poll for new reports; stop with Ctrl+C")
parser.add_argument("--poll-seconds", type=int, default=5)
parser.add_argument("--metrics-port", type=int, help="Optional loopback Prometheus port")
args = parser.parse_args()
if not 1 <= args.limit <= 1000:
    parser.error("limit must be 1..1000")
if not 1 <= args.poll_seconds <= 60:
    parser.error("poll-seconds must be 1..60")
if args.metrics_port is not None and not 1024 <= args.metrics_port <= 65535:
    parser.error("metrics-port must be 1024..65535")
metadata = json.loads(Path("models/bge-m3/PROVENANCE.json").read_text(encoding="utf-8"))
revision = f"bge-m3:{metadata['revision']}:dense:tokens512:v1"
engine = make_engine(Settings().database_url)
if engine.dialect.name != "postgresql":
    raise RuntimeError("PostgreSQL with pgvector is required")
tenant = str(args.tenant)
model = None
database_failures = 0
metrics = EmbeddingMetrics(args.metrics_port)
try:
    while True:
        processed = 0
        try:
            rows = pending_reports(engine, tenant, revision, args.limit)
            metrics.pending.set(len(rows))
            if rows:
                if model is None:
                    model = LocalBgeM3("models/bge-m3")
                processed = embed_batch(engine, tenant, revision, model, rows, metrics=metrics)
            database_failures = 0
        except OperationalError:
            database_failures += 1
            if not args.watch or database_failures >= 5:
                raise SystemExit("DATABASE_UNAVAILABLE: restart after database recovery") from None
            engine.dispose()
            print(json.dumps({"event": "DATABASE_RETRY", "attempt": database_failures}), flush=True)
            time.sleep(min(2**database_failures, 30))
            continue
        except Exception:
            raise SystemExit("EMBEDDING_FAILURE: inspect model pack and database health") from None
        if rows or not args.watch:
            print(json.dumps({"processed": processed, "model_revision": revision}), flush=True)
        if not args.watch:
            break
        time.sleep(args.poll_seconds)
except KeyboardInterrupt:
    print("Local embedding worker stopped; committed vectors retained", flush=True)
finally:
    engine.dispose()
