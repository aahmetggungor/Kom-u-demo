"""Tenant-scoped, same-revision semantic retrieval. Suggestions never mutate cases."""

import math

from sqlalchemy import text

from .ai import multi_signal_duplicate_evidence


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
            SELECT r.id, r.occurred_at, r.address_raw, r.analysis, e.embedding,
                sc.location_status,
                CASE WHEN sc.location_status='CONFIRMED' THEN sc.lat ELSE r.reported_lat END AS source_lat,
                CASE WHEN sc.location_status='CONFIRMED' THEN sc.lon ELSE r.reported_lon END AS source_lon
            FROM reports r JOIN report_embeddings e
              ON e.tenant_id=r.tenant_id AND e.report_id=r.id AND e.model_revision=:revision
            JOIN cases sc ON sc.tenant_id=r.tenant_id AND sc.id=r.case_id
            WHERE r.tenant_id=:tenant AND r.case_id=:case_id
        ), candidates AS (
            SELECT c.id AS case_id, r.id AS report_id, s.id AS source_report_id,
                1-(e.embedding <=> s.embedding) AS semantic_similarity,
                abs(extract(epoch FROM (r.occurred_at-s.occurred_at))) AS time_delta_seconds,
                s.address_raw AS source_address, r.address_raw AS candidate_address,
                s.analysis AS source_analysis, r.analysis AS candidate_analysis,
                s.location_status AS source_location_status,
                c.location_status AS candidate_location_status,
                CASE WHEN
                    (CASE WHEN c.location_status='CONFIRMED' THEN c.lat ELSE r.reported_lat END) IS NOT NULL
                    AND s.source_lat IS NOT NULL
                    THEN ST_Distance(
                        ST_SetSRID(ST_MakePoint(
                            CASE WHEN c.location_status='CONFIRMED' THEN c.lon ELSE r.reported_lon END,
                            CASE WHEN c.location_status='CONFIRMED' THEN c.lat ELSE r.reported_lat END
                        ),4326)::geography,
                        ST_SetSRID(ST_MakePoint(s.source_lon,s.source_lat),4326)::geography)
                    ELSE NULL END AS distance_m,
                row_number() OVER (PARTITION BY c.id ORDER BY e.embedding <=> s.embedding, r.id, s.id) AS rank
            FROM source_reports s CROSS JOIN report_embeddings e
            JOIN reports r ON r.tenant_id=e.tenant_id AND r.id=e.report_id
            JOIN cases c ON c.tenant_id=r.tenant_id AND c.id=r.case_id
            WHERE e.tenant_id=:tenant AND e.model_revision=:revision
              AND c.id<>:case_id AND c.status='OPEN'
              AND r.occurred_at BETWEEN s.occurred_at-interval '24 hours' AND s.occurred_at+interval '24 hours'
        ) SELECT * FROM candidates WHERE rank=1
        ORDER BY semantic_similarity DESC, case_id LIMIT :pool
    """),
            {
                "tenant": tenant_id,
                "case_id": case_id,
                "revision": revision,
                "pool": max(20, limit * 10),
            },
        )
        .mappings()
        .all()
    )
    results = []
    for row in rows:
        source_analysis = row["source_analysis"] or {}
        candidate_analysis = row["candidate_analysis"] or {}
        if row["distance_m"] is None:
            location_basis = "MISSING"
        elif (
            row["source_location_status"] == "CONFIRMED"
            and row["candidate_location_status"] == "CONFIRMED"
        ):
            location_basis = "BOTH_CONFIRMED"
        else:
            location_basis = "REPORTED_OR_MIXED"
        evidence = multi_signal_duplicate_evidence(
            max(-1.0, min(1.0, float(row["semantic_similarity"]))),
            float(row["distance_m"]) if row["distance_m"] is not None else None,
            float(row["time_delta_seconds"]),
            row["source_address"],
            row["candidate_address"],
            source_analysis.get("needs", []),
            candidate_analysis.get("needs", []),
            location_basis,
        )
        results.append(
            {
                "case_id": row["case_id"],
                "report_id": row["report_id"],
                "source_report_id": row["source_report_id"],
                "semantic_similarity": max(-1.0, min(1.0, float(row["semantic_similarity"]))),
                "distance_m": float(row["distance_m"]) if row["distance_m"] is not None else None,
                "time_delta_seconds": float(row["time_delta_seconds"]),
                "model_revision": revision,
                "human_review_required": True,
                "building_identity": evidence.address_identity,
                "suggested_for_review": evidence.propose_merge,
                "multi_signal_score": round(evidence.score, 6),
                "signals": {
                    "semantic": round(evidence.semantic_similarity, 6),
                    "location": round(evidence.location_similarity, 6),
                    "time": round(evidence.time_similarity, 6),
                    "address": round(evidence.entity_similarity, 6),
                    "needs": round(evidence.needs_similarity, 6),
                },
                "contributions": {name: round(value, 6) for name, value in evidence.contributions},
                "blockers": list(evidence.blockers),
                "location_basis": evidence.location_basis,
                "recommendation": evidence.reason,
            }
        )
    return sorted(
        results,
        key=lambda item: (
            item["suggested_for_review"],
            item["multi_signal_score"],
            item["semantic_similarity"],
        ),
        reverse=True,
    )[:limit]
