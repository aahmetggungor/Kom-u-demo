"""Human-only regrouping. Original report content and historical case rows survive."""

from fastapi import HTTPException
from sqlalchemy import select

from .domain import audit, emit, get_case, serialize_tenant
from .models import Case, Job, Report, ReviewHistory, utcnow
from .security import require_role


def check_case(case, version):
    if case.status != "OPEN" or case.version != version:
        raise HTTPException(409, "Only unchanged open cases can be regrouped")


def reports_for(session, tenant, ids):
    reports = session.scalars(
        select(Report).where(Report.tenant_id == tenant, Report.case_id.in_(ids))
    ).all()
    if not reports or len(reports) > 100:
        raise HTTPException(409, "Development grouping supports 1 to 100 reports")
    running = session.scalar(
        select(Job.id)
        .where(
            Job.tenant_id == tenant,
            Job.report_id.in_([r.id for r in reports]),
            Job.state.in_(["QUEUED", "RUNNING"]),
        )
        .limit(1)
    )
    if running:
        raise HTTPException(409, "Wait for pending analysis before regrouping")
    return reports


def require_reason(reason):
    if len(reason.strip()) < 3:
        raise HTTPException(422, "A meaningful review reason is required")


def reset_review(case, reports):
    # Regrouping changes the evidence; prior coordinates/dispatch approval must not carry over.
    case.verification_status = "UNVERIFIED"
    case.human_review_required = True
    case.location_status = "AMBIGUOUS_LOCATION"
    case.lat = case.lon = None
    case.assigned_team_id = None
    case.region = None
    kinds = {report.analysis.get("incident_type", "unknown") for report in reports}
    case.incident_type = next(iter(kinds)) if len(kinds) == 1 else "unknown"
    case.urgency_level = "UNKNOWN"
    case.ai_confidence = 0
    case.needs = sorted({need for report in reports for need in report.analysis.get("needs", [])})
    case.version += 1
    case.updated_at = utcnow()


def history(session, actor, case, action, reason, metadata):
    session.add(
        ReviewHistory(
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            case_id=case.id,
            version=case.version,
            reason=reason,
        )
    )
    audit(
        session,
        actor,
        action,
        case.id,
        {**metadata, "version": case.version, "reason_recorded": True},
    )
    emit(session, case, action)


def merge(session, actor, source_id, payload):
    require_role(actor, "admin", "coordinator")
    require_reason(payload.reason)
    target_id = str(payload.target_case_id)
    if source_id == target_id:
        raise HTTPException(422, "Source and target must differ")
    serialize_tenant(session, actor.tenant_id)
    source = get_case(session, actor.tenant_id, source_id)
    target = get_case(session, actor.tenant_id, target_id)
    check_case(source, payload.expected_source_version)
    check_case(target, payload.expected_target_version)
    reports = reports_for(session, actor.tenant_id, [source.id, target.id])
    moved = [r for r in reports if r.case_id == source.id]
    if not moved or len(moved) == len(reports):
        raise HTTPException(409, "Both cases must contain reports")
    for report in moved:
        report.case_id = target.id
    source.status = "MERGED"
    source.merged_into_id = target.id
    source.version += 1
    source.updated_at = utcnow()
    reset_review(target, reports)
    history(
        session,
        actor,
        source,
        "case.merged",
        payload.reason,
        {"target_case_id": target.id, "report_ids": [r.id for r in moved]},
    )
    history(
        session, actor, target, "case.merge_received", payload.reason, {"source_case_id": source.id}
    )
    session.commit()
    return target


def split(session, actor, case_id, payload):
    require_role(actor, "admin", "coordinator")
    require_reason(payload.reason)
    serialize_tenant(session, actor.tenant_id)
    source = get_case(session, actor.tenant_id, case_id)
    check_case(source, payload.expected_version)
    reports = reports_for(session, actor.tenant_id, [source.id])
    selected = {str(value) for value in payload.report_ids}
    if len(selected) != len(payload.report_ids) or not selected < {r.id for r in reports}:
        raise HTTPException(422, "Select a unique proper subset of this case's reports")
    moved = [r for r in reports if r.id in selected]
    remaining = [r for r in reports if r.id not in selected]
    target = Case(tenant_id=actor.tenant_id)
    session.add(target)
    session.flush()
    for report in moved:
        report.case_id = target.id
    reset_review(target, moved)
    reset_review(source, remaining)
    history(
        session,
        actor,
        source,
        "case.split",
        payload.reason,
        {"target_case_id": target.id, "report_ids": sorted(selected)},
    )
    history(
        session, actor, target, "case.split_created", payload.reason, {"source_case_id": source.id}
    )
    session.commit()
    return target
