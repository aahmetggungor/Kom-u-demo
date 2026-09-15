"""Restartable local embedding batches. Original reports remain the durable input."""

import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .db import tenant_session
from .semantic import store_embedding


def pending_reports(engine, tenant_id, revision, limit=100):
    if not 1 <= limit <= 1000:
        raise ValueError("Batch limit must be 1..1000")
    with tenant_session(engine, tenant_id) as session:
        return session.execute(
            text("""
            SELECT r.id, r.original_text FROM reports r
            WHERE r.tenant_id=:tenant AND NOT EXISTS (
                SELECT 1 FROM report_embeddings e WHERE e.tenant_id=r.tenant_id
                AND e.report_id=r.id AND e.model_revision=:revision)
            ORDER BY r.created_at, r.id LIMIT :limit
        """),
            {"tenant": tenant_id, "revision": revision, "limit": limit},
        ).all()


def embed_batch(engine, tenant_id, revision, model, rows, metrics=None):
    count = 0
    for offset in range(0, len(rows), 4):
        batch = rows[offset : offset + 4]
        started = time.monotonic()
        try:
            vectors = model.encode([row.original_text for row in batch])
            inserted = 0
            with tenant_session(engine, tenant_id) as session:
                for row, vector in zip(batch, vectors, strict=True):
                    inserted += store_embedding(session, tenant_id, row.id, revision, vector)
                session.commit()
        except Exception as exc:
            if metrics:
                result = "database_error" if isinstance(exc, SQLAlchemyError) else "model_error"
                metrics.observe_batch(result, 0, time.monotonic() - started)
            raise
        if metrics:
            metrics.observe_batch("done", inserted, time.monotonic() - started)
        count += inserted
    return count
