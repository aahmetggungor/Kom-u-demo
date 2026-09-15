import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .models import Audit, Case, Dispatch, Event, Job, Organization, Report, Team, uid, utcnow
from .schemas import DispatchIn, ReportIn, ReviewIn
from .security import Principal, require_role


def serialize_tenant(session, tenant_id: str):
    # Serialises event-producing transactions per tenant, preserving event cursor commit order.
    if session.bind.dialect.name == "sqlite":
        session.execute(
            update(Organization).where(Organization.id == tenant_id).values(id=Organization.id)
        )
    session.execute(
        select(Organization.id).where(Organization.id == tenant_id).with_for_update()
    ).scalar_one()


def audit(session, principal, action, target, detail=None):
    session.add(
        Audit(
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action=action,
            target_id=target,
            detail=detail or {},
        )
    )


def emit(session, case, kind):
    session.add(Event(tenant_id=case.tenant_id, case_id=case.id, kind=kind, version=case.version))


def get_case(session, tenant_id, case_id):
    case = session.scalar(select(Case).where(Case.tenant_id == tenant_id, Case.id == case_id))
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


def payload_digest(payload: ReportIn):
    # UUID identity spans relay transports; source is provenance of first delivery, not payload identity.
    canonical = payload.model_dump(mode="json", exclude={"source"})
    return hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def ingest(session, principal: Principal, payload: ReportIn, queue_limit: int):
    require_role(principal, "admin", "coordinator", "rescue-team")
    serialize_tenant(session, principal.tenant_id)
    digest = payload_digest(payload)
    existing = session.scalar(
        select(Report).where(
            Report.tenant_id == principal.tenant_id, Report.client_id == str(payload.client_id)
        )
    )
    if existing:
        if existing.payload_hash != digest:
            raise HTTPException(409, "UUID already exists with different payload")
        return existing, True
    pending = session.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.tenant_id == principal.tenant_id, Job.state.in_(["QUEUED", "RUNNING"]))
    )
    if pending >= queue_limit:
        raise HTTPException(
            503, "Processing queue full; keep local report and retry", headers={"Retry-After": "30"}
        )
    case = Case(id=uid(), tenant_id=principal.tenant_id, version=1)
    session.add(case)
    session.flush()
    report = Report(
        id=uid(),
        tenant_id=principal.tenant_id,
        client_id=str(payload.client_id),
        case_id=case.id,
        actor_id=principal.user_id,
        source=payload.source.value,
        original_text=payload.text,
        original_language=payload.language,
        address_raw=payload.address_raw,
        reported_lat=payload.location.lat if payload.location else None,
        reported_lon=payload.location.lon if payload.location else None,
        occurred_at=payload.occurred_at,
        payload_hash=digest,
    )
    session.add(report)
    session.flush()
    session.add(Job(tenant_id=principal.tenant_id, report_id=report.id))
    audit(session, principal, "report.received", report.id)
    emit(session, case, "case.created")
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(Report).where(
                Report.tenant_id == principal.tenant_id, Report.client_id == str(payload.client_id)
            )
        )
        if existing and existing.payload_hash == digest:
            return existing, True
        raise HTTPException(409, "Concurrent report conflict") from None
    return report, False


def review(session, principal, case_id: str, payload: ReviewIn):
    require_role(principal, "admin", "coordinator")
    serialize_tenant(session, principal.tenant_id)
    case = get_case(session, principal.tenant_id, case_id)
    if case.status != "OPEN":
        raise HTTPException(409, "Only open cases can be reviewed")
    values = {
        "verification_status": payload.verification_status,
        "urgency_level": payload.urgency_level,
        "region": payload.region,
        "human_review_required": payload.verification_status != "VERIFIED",
        "version": Case.version + 1,
        "updated_at": utcnow(),
    }
    if payload.location:
        values.update(
            lat=payload.location.lat,
            lon=payload.location.lon,
            location_status="CONFIRMED" if payload.confirm_location else "UNCONFIRMED",
        )
    result = session.execute(
        update(Case)
        .where(
            Case.id == case_id,
            Case.tenant_id == principal.tenant_id,
            Case.version == payload.expected_version,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Case changed; reload before reviewing")
    session.refresh(case)
    # Do not copy potentially sensitive free-text reason into audit logs.
    audit(
        session,
        principal,
        "case.reviewed",
        case.id,
        {
            "version": case.version,
            "verification": case.verification_status,
            "reason_recorded": True,
        },
    )
    # Protected review history is distinct from operational audit metadata.
    from .models import ReviewHistory

    session.add(
        ReviewHistory(
            tenant_id=principal.tenant_id,
            case_id=case.id,
            actor_id=principal.user_id,
            version=case.version,
            reason=payload.reason,
        )
    )
    emit(session, case, "case.reviewed")
    session.commit()
    return case


def dispatch(session, principal, case_id: str, payload: DispatchIn):
    require_role(principal, "admin", "coordinator")
    serialize_tenant(session, principal.tenant_id)
    case = get_case(session, principal.tenant_id, case_id)
    team = session.scalar(
        select(Team).where(Team.tenant_id == principal.tenant_id, Team.id == str(payload.team_id))
    )
    if not team:
        raise HTTPException(404, "Team not found")
    if (
        case.verification_status != "VERIFIED"
        or case.location_status != "CONFIRMED"
        or case.lat is None
        or case.lon is None
    ):
        raise HTTPException(409, "Verified case and human-confirmed location required")
    result = session.execute(
        update(Case)
        .where(
            Case.id == case_id,
            Case.tenant_id == principal.tenant_id,
            Case.version == payload.expected_version,
            Case.status == "OPEN",
        )
        .values(
            status="DISPATCHED",
            assigned_team_id=team.id,
            version=Case.version + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Case changed or already dispatched")
    session.refresh(case)
    session.add(
        Dispatch(
            tenant_id=principal.tenant_id,
            case_id=case.id,
            team_id=team.id,
            actor_id=principal.user_id,
            case_version=case.version,
        )
    )
    audit(
        session,
        principal,
        "case.dispatched",
        case.id,
        {"team_id": team.id, "version": case.version},
    )
    emit(session, case, "case.dispatched")
    session.commit()
    return case
