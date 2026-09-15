"""Tenant-scoped, same-revision semantic retrieval. Suggestions never mutate cases."""

import math

from sqlalchemy import text


def vector_literal(vector):
    if len(vector) != 1024 or any(
        type(n) not in (float, int) or not math.isfinite(n) for n in vector
    ):
        raise ValueError("Expected 1024 finite embedding components")
    if sum(n * n for n in vector) < 1e-12:
        raise ValueError("Zero embeddings cannot be compared")
    return "[" + ",".join(format(n, ".9g") for n in vector) + "]"


def store_embedding(session, tenant_id, report_id, revision, vector):
    if not revision or len(revision) > 160:
        raise ValueError("Bounded model revision required")
    result = session.execute(
        text("""
        INSERT INTO report_embeddings (tenant_id, report_id, model_revision, embedding)
        VALUES (:tenant, :report, :revision, CAST(:embedding AS vector))
        ON CONFLICT (tenant_id, report_id, model_revision) DO NOTHING
    """),
        {
            "tenant": tenant_id,
            "report": report_id,
            "revision": revision,
            "embedding": vector_literal(vector),
        },
    )
    return result.rowcount


def similar_cases(session, tenant_id, case_id, revision, limit=5):
    if not 1 <= limit <= 10:
        raise ValueError("Bounded candidate limit required")
    # Exact top-k is intentional at development scale; ANN tenant recall must be measured first.
    # Location is measured from each original report; confirmed case positions are not inferred.
    rows = (
        session.execute(
            text("""
        WITH source_reports AS (
            SELECT r.id, r.occurred_at, r.reported_lat, r.reported_lon, e.embedding
            FROM reports r JOIN report_embeddings e
              ON e.tenant_id=r.tenant_id AND e.report_id=r.id AND e.model_revision=:revision
            WHERE r.tenant_id=:tenant AND r.case_id=:case_id
        ), candidates AS (
            SELECT c.id AS case_id, r.id AS report_id, s.id AS source_report_id,
                1-(e.embedding <=> s.embedding) AS semantic_similarity,
                abs(extract(epoch FROM (r.occurred_at-s.occurred_at))) AS time_delta_seconds,
                CASE WHEN r.reported_lat IS NOT NULL AND s.reported_lat IS NOT NULL
                    THEN ST_Distance(
                        ST_SetSRID(ST_MakePoint(r.reported_lon,r.reported_lat),4326)::geography,
                        ST_SetSRID(ST_MakePoint(s.reported_lon,s.reported_lat),4326)::geography)
                    ELSE NULL END AS distance_m,
                row_number() OVER (PARTITION BY c.id ORDER BY e.embedding <=> s.embedding, r.id, s.id) AS rank
            FROM source_reports s CROSS JOIN report_embeddings e
            JOIN reports r ON r.tenant_id=e.tenant_id AND r.id=e.report_id
            JOIN cases c ON c.tenant_id=r.tenant_id AND c.id=r.case_id
            WHERE e.tenant_id=:tenant AND e.model_revision=:revision
              AND c.id<>:case_id AND c.status='OPEN'
              AND r.occurred_at BETWEEN s.occurred_at-interval '24 hours' AND s.occurred_at+interval '24 hours'
        ) SELECT * FROM candidates WHERE rank=1
        ORDER BY semantic_similarity DESC, case_id LIMIT :limit
    """),
            {"tenant": tenant_id, "case_id": case_id, "revision": revision, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        {
            "case_id": row["case_id"],
            "report_id": row["report_id"],
            "source_report_id": row["source_report_id"],
            "semantic_similarity": max(-1.0, min(1.0, float(row["semantic_similarity"]))),
            "distance_m": float(row["distance_m"]) if row["distance_m"] is not None else None,
            "time_delta_seconds": float(row["time_delta_seconds"]),
            "model_revision": revision,
            "human_review_required": True,
            "building_identity": "NOT_VERIFIED",
            "recommendation": "COMPARE_ORIGINAL_REPORTS",
        }
        for row in rows
    ]
