"""Two-person retention scheduling and explicit administrative execution."""

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from .domain import audit, serialize_tenant
from .models import (
    AudioAsset,
    Case,
    InboundDelivery,
    LegalHold,
    MapLayer,
    Report,
    RetentionPlan,
    ReviewHistory,
    uid,
    utcnow,
)
from .security import require_role


def plan_json(session, plan):
    report_count = session.scalar(
        select(func.count())
        .select_from(Report)
        .where(Report.tenant_id == plan.tenant_id, Report.occurred_at <= plan.cutoff_at)
    )
    audio_count = session.scalar(
        select(func.count())
        .select_from(AudioAsset)
        .join(
            Report,
            (Report.tenant_id == AudioAsset.tenant_id) & (Report.id == AudioAsset.report_id),
        )
        .where(Report.tenant_id == plan.tenant_id, Report.occurred_at <= plan.cutoff_at)
    )
    inbound_count = session.scalar(
        select(func.count())
        .select_from(InboundDelivery)
        .where(
            InboundDelivery.tenant_id == plan.tenant_id,
            or_(
                InboundDelivery.received_at <= plan.cutoff_at,
                InboundDelivery.report_id.in_(
                    select(Report.id).where(
                        Report.tenant_id == plan.tenant_id,
                        Report.occurred_at <= plan.cutoff_at,
                    )
                ),
            ),
        )
    )
    return {
        "id": plan.id,
        "status": plan.status,
        "cutoff_at": plan.cutoff_at.isoformat(),
        "execute_after": plan.execute_after.isoformat(),
        "reason_code": plan.reason_code,
        "requested_by": plan.requested_by,
        "approved_by": plan.approved_by,
        "requested_at": plan.requested_at.isoformat(),
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "executed_at": plan.executed_at.isoformat() if plan.executed_at else None,
        "preview_report_count": report_count if plan.status != "EXECUTED" else None,
        "preview_audio_count": audio_count if plan.status != "EXECUTED" else None,
        "preview_inbound_receipt_count": inbound_count if plan.status != "EXECUTED" else None,
        "result_counts": plan.result_counts,
        "requires_distinct_approver": True,
    }


def schedule(session, actor, payload):
    require_role(actor, "admin")
    serialize_tenant(session, actor.tenant_id)
    existing = session.scalar(
        select(RetentionPlan)
        .where(
            RetentionPlan.tenant_id == actor.tenant_id,
            RetentionPlan.status.in_(["SCHEDULED", "APPROVED"]),
        )
        .with_for_update()
    )
    if existing:
        from fastapi import HTTPException

        raise HTTPException(409, "An active retention plan already exists")
    plan = RetentionPlan(
        id=uid(),
        tenant_id=actor.tenant_id,
        cutoff_at=payload.cutoff_at,
        execute_after=payload.execute_after,
        reason_code=payload.reason_code,
        requested_by=actor.user_id,
        status="SCHEDULED",
    )
    session.add(plan)
    session.flush()
    audit(
        session,
        actor,
        "retention.scheduled",
        plan.id,
        {
            "cutoff_at": payload.cutoff_at.isoformat(),
            "execute_after": payload.execute_after.isoformat(),
            "reason_code": payload.reason_code,
        },
    )
    session.commit()
    return plan


def approve(session, actor, plan_id, payload):
    require_role(actor, "admin")
    serialize_tenant(session, actor.tenant_id)
    plan = session.scalar(
        select(RetentionPlan)
        .where(RetentionPlan.tenant_id == actor.tenant_id, RetentionPlan.id == plan_id)
        .with_for_update()
    )
    if plan is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Retention plan not found")
    if plan.status != payload.expected_status:
        from fastapi import HTTPException

        raise HTTPException(409, "Retention plan status changed")
    if plan.requested_by == actor.user_id:
        from fastapi import HTTPException

        raise HTTPException(409, "A distinct administrator must approve the plan")
    plan.status = "APPROVED"
    plan.approved_by = actor.user_id
    plan.approved_at = utcnow()
    audit(session, actor, "retention.approved", plan.id, {"reason_code": plan.reason_code})
    session.commit()
    return plan


def cancel(session, actor, plan_id, payload):
    require_role(actor, "admin")
    serialize_tenant(session, actor.tenant_id)
    plan = session.scalar(
        select(RetentionPlan)
        .where(RetentionPlan.tenant_id == actor.tenant_id, RetentionPlan.id == plan_id)
        .with_for_update()
    )
    if plan is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Retention plan not found")
    if plan.status != payload.expected_status:
        from fastapi import HTTPException

        raise HTTPException(409, "Retention plan status changed")
    plan.status = "CANCELLED"
    audit(session, actor, "retention.cancelled", plan.id, {"reason_code": payload.reason_code})
    session.commit()
    return plan


def create_hold(session, actor, payload):
    require_role(actor, "admin")
    serialize_tenant(session, actor.tenant_id)
    hold = LegalHold(
        id=uid(),
        tenant_id=actor.tenant_id,
        reason_code=payload.reason_code,
        expires_at=payload.expires_at,
        created_by=actor.user_id,
    )
    session.add(hold)
    session.flush()
    audit(
        session,
        actor,
        "retention.hold_created",
        hold.id,
        {"reason_code": hold.reason_code, "expires_at": hold.expires_at.isoformat()},
    )
    session.commit()
    return hold


def hold_json(hold):
    active = hold.released_at is None and hold.expires_at > utcnow()
    return {
        "id": hold.id,
        "reason_code": hold.reason_code,
        "expires_at": hold.expires_at.isoformat(),
        "created_by": hold.created_by,
        "created_at": hold.created_at.isoformat(),
        "released_at": hold.released_at.isoformat() if hold.released_at else None,
        "active": active,
    }


def release_hold(session, actor, hold_id, payload):
    require_role(actor, "admin")
    serialize_tenant(session, actor.tenant_id)
    hold = session.scalar(
        select(LegalHold)
        .where(LegalHold.tenant_id == actor.tenant_id, LegalHold.id == hold_id)
        .with_for_update()
    )
    if hold is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Legal hold not found")
    if hold.released_at is not None or hold.expires_at <= utcnow():
        from fastapi import HTTPException

        raise HTTPException(409, "Legal hold is no longer active")
    hold.released_at = utcnow()
    audit(
        session,
        actor,
        "retention.hold_released",
        hold.id,
        {"reason_code": payload.reason_code},
    )
    session.commit()
    return hold


def execute(admin_engine, plan_id, confirmation):
    if confirmation != plan_id:
        raise ValueError("Confirmation must exactly match the plan id")
    with Session(admin_engine, expire_on_commit=False) as session:
        plan = session.scalar(
            select(RetentionPlan).where(RetentionPlan.id == plan_id).with_for_update()
        )
        if plan is None or plan.status != "APPROVED":
            raise ValueError("Plan is not approved")
        if plan.execute_after > utcnow():
            raise ValueError("Plan execution time has not arrived")
        active_hold = session.scalar(
            select(LegalHold.id).where(
                LegalHold.tenant_id == plan.tenant_id,
                LegalHold.released_at.is_(None),
                LegalHold.expires_at > utcnow(),
            )
        )
        if active_hold:
            raise ValueError("An active legal hold blocks retention execution")
        report_ids = select(Report.id).where(
            Report.tenant_id == plan.tenant_id, Report.occurred_at <= plan.cutoff_at
        )
        case_ids = select(Report.case_id).where(
            Report.tenant_id == plan.tenant_id, Report.occurred_at <= plan.cutoff_at
        )
        counts = {}
        counts["inbound_receipts_deleted"] = (
            session.query(InboundDelivery)
            .filter(
                InboundDelivery.tenant_id == plan.tenant_id,
                or_(
                    InboundDelivery.received_at <= plan.cutoff_at,
                    InboundDelivery.report_id.in_(report_ids),
                ),
            )
            .delete(synchronize_session=False)
        )
        counts["audio_assets_deleted"] = (
            session.query(AudioAsset)
            .filter(
                AudioAsset.tenant_id == plan.tenant_id,
                AudioAsset.report_id.in_(report_ids),
            )
            .delete(synchronize_session=False)
        )
        counts["embeddings_deleted"] = session.execute(
            text(
                "DELETE FROM report_embeddings WHERE tenant_id=:tenant AND report_id IN "
                "(SELECT id FROM reports WHERE tenant_id=:tenant AND occurred_at<=:cutoff)"
            ),
            {"tenant": plan.tenant_id, "cutoff": plan.cutoff_at},
        ).rowcount
        counts["reports_redacted"] = (
            session.query(Report)
            .filter(Report.id.in_(report_ids))
            .update(
                {
                    Report.original_text: "[PURGED_AFTER_RETENTION]",
                    Report.original_language: "und",
                    Report.address_raw: None,
                    Report.reported_lat: None,
                    Report.reported_lon: None,
                    Report.analysis: {"retention": "PURGED"},
                    Report.payload_hash: "0" * 64,
                },
                synchronize_session=False,
            )
        )
        counts["cases_reset"] = (
            session.query(Case)
            .filter(Case.tenant_id == plan.tenant_id, Case.id.in_(case_ids))
            .update(
                {
                    Case.lat: None,
                    Case.lon: None,
                    Case.region: None,
                    Case.needs: [],
                    Case.ai_confidence: 0.0,
                    Case.location_status: "PURGED",
                    Case.human_review_required: True,
                },
                synchronize_session=False,
            )
        )
        counts["review_reasons_redacted"] = (
            session.query(ReviewHistory)
            .filter(ReviewHistory.tenant_id == plan.tenant_id, ReviewHistory.case_id.in_(case_ids))
            .update({ReviewHistory.reason: "[PURGED_AFTER_RETENTION]"}, synchronize_session=False)
        )
        counts["map_layers_deleted"] = (
            session.query(MapLayer)
            .filter(MapLayer.tenant_id == plan.tenant_id, MapLayer.updated_at <= plan.cutoff_at)
            .delete(synchronize_session=False)
        )
        plan.status = "EXECUTED"
        plan.executed_at = utcnow()
        plan.result_counts = counts
        session.commit()
        return counts
