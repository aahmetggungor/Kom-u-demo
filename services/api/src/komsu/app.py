import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from sqlalchemy import case as sql_case
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from .audio_scanning import decide_audio
from .audio_storage import (
    ALLOWED_CONTENT_TYPES,
    AudioConfigurationError,
    AudioRejected,
    audio_json,
    derive_keys,
    store_audio,
)
from .config import Settings
from .db import make_engine, tenant_session
from .domain import audit, dispatch, get_case, ingest, review, serialize_tenant
from .grouping import merge, split
from .map_layers import LayerIn
from .models import (
    AudioAsset,
    AudioTranscript,
    Case,
    Event,
    LegalHold,
    MapLayer,
    Report,
    RetentionPlan,
    Team,
)
from .retention import approve as approve_retention
from .retention import cancel as cancel_retention
from .retention import create_hold, hold_json, plan_json, release_hold
from .retention import schedule as schedule_retention
from .schemas import (
    AudioAccepted,
    AudioDecisionIn,
    DispatchIn,
    LegalHoldIn,
    LegalHoldReleaseIn,
    MergeIn,
    ReportAccepted,
    ReportIn,
    RetentionApproveIn,
    RetentionCancelIn,
    RetentionScheduleIn,
    ReviewIn,
    SplitIn,
    TeamIn,
    TranscriptReviewIn,
)
from .security import Principal, authenticate, require_role
from .transcription_worker import review_transcript, transcript_json

logger = logging.getLogger("komsu")
bearer = HTTPBearer(auto_error=False)


def case_json(session, case):
    count = session.scalar(
        select(func.count())
        .select_from(Report)
        .where(Report.tenant_id == case.tenant_id, Report.case_id == case.id)
    )
    return {
        "id": case.id,
        "status": case.status,
        "merged_into_id": case.merged_into_id,
        "verification_status": case.verification_status,
        "urgency_level": case.urgency_level,
        "incident_type": case.incident_type,
        "needs": case.needs,
        "ai_confidence": case.ai_confidence,
        "location_status": case.location_status,
        "location": {"lat": case.lat, "lon": case.lon},
        "region": case.region,
        "human_review_required": case.human_review_required,
        "assigned_team_id": case.assigned_team_id,
        "version": case.version,
        "report_count": count,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
    }


def report_json(report, audio=None, transcript=None):
    result = {
        "id": report.id,
        "client_id": report.client_id,
        "case_id": report.case_id,
        "source": report.source,
        "original_text": report.original_text,
        "original_language": report.original_language,
        "address_raw": report.address_raw,
        "analysis": report.analysis,
        "processing_status": report.processing_status,
        "occurred_at": report.occurred_at.isoformat(),
        "created_at": report.created_at.isoformat(),
    }
    result["audio"] = audio_json(audio) if audio else None
    result["transcript"] = transcript_json(transcript)
    return result


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings()
    settings.validate_runtime()
    engine = engine or make_engine(settings.database_url)
    app = FastAPI(
        title="Komşu Coordination API",
        version="0.1.0",
        description="Human-led coordination development foundation; all AI outputs require review.",
    )
    app.state.engine = engine
    app.state.settings = settings
    registry = CollectorRegistry()
    requests = Counter(
        "komsu_http_requests_total", "HTTP requests", ["method", "status"], registry=registry
    )
    latency = Histogram("komsu_http_duration_seconds", "HTTP duration", registry=registry)
    windows = defaultdict(deque)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request_id = str(uuid4())
        start = time.monotonic()
        # Enforce actual streamed bytes, not just an untrusted Content-Length header.
        body = bytearray()
        body_limit = (
            settings.max_audio_bytes
            if request.url.path.startswith("/api/v1/reports/")
            and request.url.path.endswith("/audio")
            else settings.max_body_bytes
        )
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > body_limit:
                return JSONResponse({"detail": "Request too large"}, 413)
        request._body = bytes(body)
        try:
            response = await call_next(request)
        except SQLAlchemyError:
            logger.error(json.dumps({"event": "database_error", "request_id": request_id}))
            response = JSONResponse(
                {"detail": "Database unavailable; retry with same report UUID"},
                503,
                headers={"Retry-After": "10"},
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        requests.labels(request.method, str(response.status_code)).inc()
        latency.observe(time.monotonic() - start)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Pydantic input fields can include PII; return locations/types only.
        return JSONResponse(
            {"detail": [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]}, 422
        )

    def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials:
            raise HTTPException(401, "Bearer token required")
        actor = authenticate(engine, credentials.credentials)
        now = time.monotonic()
        bucket = windows[actor.tenant_id]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= settings.requests_per_minute:
            raise HTTPException(429, "Tenant request limit reached", headers={"Retry-After": "60"})
        bucket.append(now)
        return actor

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if revision != "0008":
                raise ValueError("migration mismatch")
        except (SQLAlchemyError, ValueError):
            raise HTTPException(503, "Database/schema not ready") from None
        return {"status": "ready", "ai": "baseline_review_required"}

    @app.get("/api/v1/auth/me")
    def me(actor: Principal = Depends(principal)):
        return {"tenant_id": actor.tenant_id, "user_id": actor.user_id, "role": actor.role}

    @app.get("/metrics", include_in_schema=False)
    def metrics(actor: Principal = Depends(principal)):
        require_role(actor, "admin")
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.get("/api/v1/retention/plans")
    def retention_plans(actor: Principal = Depends(principal)):
        require_role(actor, "admin")
        with tenant_session(engine, actor.tenant_id) as session:
            plans = session.scalars(
                select(RetentionPlan)
                .where(RetentionPlan.tenant_id == actor.tenant_id)
                .order_by(RetentionPlan.requested_at.desc())
                .limit(100)
            ).all()
            return {"items": [plan_json(session, plan) for plan in plans]}

    @app.post("/api/v1/retention/plans", status_code=201)
    def create_retention_plan(payload: RetentionScheduleIn, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return plan_json(session, schedule_retention(session, actor, payload))

    @app.post("/api/v1/retention/plans/{plan_id}/approve")
    def approve_retention_plan(
        plan_id: UUID, payload: RetentionApproveIn, actor: Principal = Depends(principal)
    ):
        with tenant_session(engine, actor.tenant_id) as session:
            return plan_json(session, approve_retention(session, actor, str(plan_id), payload))

    @app.post("/api/v1/retention/plans/{plan_id}/cancel")
    def cancel_retention_plan(
        plan_id: UUID, payload: RetentionCancelIn, actor: Principal = Depends(principal)
    ):
        with tenant_session(engine, actor.tenant_id) as session:
            return plan_json(session, cancel_retention(session, actor, str(plan_id), payload))

    @app.get("/api/v1/retention/holds")
    def legal_holds(actor: Principal = Depends(principal)):
        require_role(actor, "admin")
        with tenant_session(engine, actor.tenant_id) as session:
            holds = session.scalars(
                select(LegalHold)
                .where(LegalHold.tenant_id == actor.tenant_id)
                .order_by(LegalHold.created_at.desc())
                .limit(100)
            ).all()
            return {"items": [hold_json(hold) for hold in holds]}

    @app.post("/api/v1/retention/holds", status_code=201)
    def add_legal_hold(payload: LegalHoldIn, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return hold_json(create_hold(session, actor, payload))

    @app.post("/api/v1/retention/holds/{hold_id}/release")
    def remove_legal_hold(
        hold_id: UUID, payload: LegalHoldReleaseIn, actor: Principal = Depends(principal)
    ):
        with tenant_session(engine, actor.tenant_id) as session:
            return hold_json(release_hold(session, actor, str(hold_id), payload))

    @app.post("/api/v1/reports", response_model=ReportAccepted, status_code=202)
    def receive(payload: ReportIn, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            report, replayed = ingest(session, actor, payload, settings.queue_limit)
            return ReportAccepted(
                report_id=report.id,
                case_id=report.case_id,
                processing_status=report.processing_status,
                replayed=replayed,
            )

    @app.post(
        "/api/v1/reports/{report_id}/audio",
        response_model=AudioAccepted,
        status_code=201,
        responses={200: {"description": "Identical audio replay"}},
    )
    async def receive_audio(
        report_id: UUID, request: Request, actor: Principal = Depends(principal)
    ):
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(415, "Only audio/wav is accepted")
        if settings.audio_master_key_b64 is None:
            raise HTTPException(503, "Encrypted audio storage is not configured")
        try:
            derive_keys(settings.audio_master_key_b64)
        except AudioConfigurationError:
            raise HTTPException(503, "Encrypted audio storage is not configured") from None
        payload = await request.body()
        with tenant_session(engine, actor.tenant_id) as session:
            report = session.scalar(
                select(Report).where(
                    Report.id == str(report_id), Report.tenant_id == actor.tenant_id
                )
            )
            if report is None:
                raise HTTPException(404, "Report not found")
            try:
                asset, replayed = store_audio(
                    session,
                    actor,
                    report,
                    payload,
                    settings.audio_master_key_b64,
                    settings.audio_key_id,
                    settings.max_audio_bytes,
                )
            except AudioRejected as exc:
                raise HTTPException(422, str(exc)) from None
            return JSONResponse(audio_json(asset, replayed), status_code=200 if replayed else 201)

    @app.post(
        "/api/v1/reports/{report_id}/audio/decision",
        response_model=AudioAccepted,
    )
    def audio_decision(
        report_id: UUID, payload: AudioDecisionIn, actor: Principal = Depends(principal)
    ):
        with tenant_session(engine, actor.tenant_id) as session:
            asset, replayed = decide_audio(session, actor, str(report_id), payload)
            return audio_json(asset, replayed)

    @app.post("/api/v1/reports/{report_id}/audio/transcript/review")
    def audio_transcript_review(
        report_id: UUID, payload: TranscriptReviewIn, actor: Principal = Depends(principal)
    ):
        with tenant_session(engine, actor.tenant_id) as session:
            row, replayed = review_transcript(session, actor, str(report_id), payload)
            return {**transcript_json(row), "replayed": replayed}

    @app.get("/api/v1/reports/{report_id}")
    def report_detail(report_id: UUID, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            report = session.scalar(
                select(Report).where(
                    Report.id == str(report_id), Report.tenant_id == actor.tenant_id
                )
            )
            if report is None:
                raise HTTPException(404, "Report not found")
            audio = session.scalar(
                select(AudioAsset).where(
                    AudioAsset.tenant_id == actor.tenant_id, AudioAsset.report_id == report.id
                )
            )
            transcript = session.scalar(
                select(AudioTranscript).where(
                    AudioTranscript.tenant_id == actor.tenant_id,
                    AudioTranscript.report_id == report.id,
                )
            )
            return report_json(report, audio, transcript)

    @app.get("/api/v1/cases")
    def cases(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=10000),
        urgency: str | None = None,
        incident_type: str | None = None,
        verification: str | None = None,
        language: str | None = None,
        status: str | None = None,
        region: str | None = None,
        team_id: UUID | None = None,
        since: datetime | None = None,
        actor: Principal = Depends(principal),
    ):
        with tenant_session(engine, actor.tenant_id) as session:
            query = select(Case).where(Case.tenant_id == actor.tenant_id)
            if status is None:
                query = query.where(Case.status != "MERGED")
            for column, value in [
                (Case.urgency_level, urgency),
                (Case.incident_type, incident_type),
                (Case.verification_status, verification),
                (Case.status, status),
                (Case.region, region),
                (Case.assigned_team_id, str(team_id) if team_id else None),
            ]:
                if value is not None:
                    query = query.where(column == value)
            if language:
                query = query.where(
                    Case.id.in_(
                        select(Report.case_id).where(
                            Report.tenant_id == actor.tenant_id,
                            Report.original_language == language,
                        )
                    )
                )
            if since:
                if since.tzinfo is None:
                    raise HTTPException(422, "since must include timezone")
                query = query.where(Case.created_at >= since)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            rank = sql_case(
                {"CRITICAL": 0, "UNKNOWN": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4},
                value=Case.urgency_level,
                else_=1,
            )
            records = session.scalars(
                query.order_by(rank, Case.created_at, Case.id).offset(offset).limit(limit)
            ).all()
            return {
                "items": [case_json(session, x) for x in records],
                "total": total,
                "offset": offset,
                "limit": limit,
            }

    @app.get("/api/v1/cases/{case_id}")
    def case_detail(case_id: UUID, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            case = get_case(session, actor.tenant_id, str(case_id))
            result = case_json(session, case)
            reports = session.scalars(
                select(Report)
                .where(Report.tenant_id == actor.tenant_id, Report.case_id == case.id)
                .order_by(Report.created_at)
                .limit(100)
            ).all()
            audio_by_report = (
                {
                    asset.report_id: asset
                    for asset in session.scalars(
                        select(AudioAsset).where(
                            AudioAsset.tenant_id == actor.tenant_id,
                            AudioAsset.report_id.in_([report.id for report in reports]),
                        )
                    ).all()
                }
                if reports
                else {}
            )
            transcripts_by_report = (
                {
                    row.report_id: row
                    for row in session.scalars(
                        select(AudioTranscript).where(
                            AudioTranscript.tenant_id == actor.tenant_id,
                            AudioTranscript.report_id.in_([report.id for report in reports]),
                        )
                    ).all()
                }
                if reports
                else {}
            )
            result["reports"] = [
                report_json(
                    report,
                    audio_by_report.get(report.id),
                    transcripts_by_report.get(report.id),
                )
                for report in reports
            ]
            return result

    @app.get("/api/v1/cases/{case_id}/similar")
    def case_similar(case_id: UUID, actor: Principal = Depends(principal)):
        from .semantic import similar_cases

        with tenant_session(engine, actor.tenant_id) as session:
            get_case(session, actor.tenant_id, str(case_id))
            enabled = bool(settings.embedding_revision and engine.dialect.name == "postgresql")
            return {
                "enabled": enabled,
                "model_revision": settings.embedding_revision if enabled else None,
                "human_review_required": True,
                "items": similar_cases(
                    session, actor.tenant_id, str(case_id), settings.embedding_revision
                )
                if enabled
                else [],
            }

    @app.post("/api/v1/cases/{case_id}/merge")
    def merge_case(case_id: UUID, payload: MergeIn, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return case_json(session, merge(session, actor, str(case_id), payload))

    @app.post("/api/v1/cases/{case_id}/split")
    def split_case(case_id: UUID, payload: SplitIn, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return case_json(session, split(session, actor, str(case_id), payload))

    @app.post("/api/v1/cases/{case_id}/review")
    def review_case(case_id: UUID, payload: ReviewIn, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return case_json(session, review(session, actor, str(case_id), payload))

    @app.post("/api/v1/cases/{case_id}/dispatch")
    def dispatch_case(case_id: UUID, payload: DispatchIn, actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return case_json(session, dispatch(session, actor, str(case_id), payload))

    @app.get("/api/v1/teams")
    def teams(actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return [
                {"id": t.id, "name": t.name}
                for t in session.scalars(
                    select(Team).where(Team.tenant_id == actor.tenant_id).limit(200)
                )
            ]

    @app.post("/api/v1/teams", status_code=201)
    def create_team(payload: TeamIn, actor: Principal = Depends(principal)):
        require_role(actor, "admin", "coordinator")
        with tenant_session(engine, actor.tenant_id) as session:
            team = Team(tenant_id=actor.tenant_id, name=payload.name)
            session.add(team)
            session.flush()
            audit(session, actor, "team.created", team.id)
            session.commit()
            return {"id": team.id, "name": team.name}

    @app.post("/api/v1/map/layers", status_code=201)
    def create_layer(data: LayerIn, actor: Principal = Depends(principal)):
        require_role(actor, "admin")
        with tenant_session(engine, actor.tenant_id) as session:
            serialize_tenant(session, actor.tenant_id)
            count = session.scalar(
                select(func.count())
                .select_from(MapLayer)
                .where(MapLayer.tenant_id == actor.tenant_id)
            )
            if count >= 50:
                raise HTTPException(409, "Development layer limit reached")
            row = MapLayer(tenant_id=actor.tenant_id, **data.model_dump())
            session.add(row)
            session.flush()
            audit(session, actor, "map_layer.created", row.id, {"kind": row.kind})
            session.commit()
            return {"id": row.id}

    @app.get("/api/v1/map/layers")
    def layers(actor: Principal = Depends(principal)):
        with tenant_session(engine, actor.tenant_id) as session:
            return [
                {
                    "id": row.id,
                    "kind": row.kind,
                    "name": row.name,
                    "geojson": row.geojson,
                    "provenance": row.provenance,
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in session.scalars(
                    select(MapLayer).where(MapLayer.tenant_id == actor.tenant_id).limit(50)
                )
            ]

    def read_events(actor, after):
        with tenant_session(engine, actor.tenant_id) as session:
            return [
                {"id": e.id, "case_id": e.case_id, "kind": e.kind, "version": e.version}
                for e in session.scalars(
                    select(Event)
                    .where(Event.tenant_id == actor.tenant_id, Event.id > after)
                    .order_by(Event.id)
                    .limit(100)
                )
            ]

    @app.get("/api/v1/events")
    def events(after: int = Query(0, ge=0), actor: Principal = Depends(principal)):
        return {"items": read_events(actor, after)}

    @app.websocket("/api/v1/events/ws")
    async def socket(ws: WebSocket):
        if ws.headers.get("origin") not in settings.allowed_origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            # First-frame auth avoids URL/access-log tokens. No PII before authentication.
            raw = await asyncio.wait_for(ws.receive_text(), timeout=5)
            if len(raw) > 1024:
                await ws.close(code=1008)
                return
            hello = json.loads(raw)
            if not isinstance(hello, dict):
                await ws.close(code=1008)
                return
            token = hello.get("token", "")
            cursor = hello.get("after", 0)
            if not isinstance(token, str) or type(cursor) is not int or cursor < 0:
                await ws.close(code=1008)
                return
            while True:
                actor = await asyncio.to_thread(authenticate, engine, token)
                batch = await asyncio.to_thread(read_events, actor, cursor)
                await ws.send_json({"items": batch, "type": "events" if batch else "heartbeat"})
                if batch:
                    cursor = batch[-1]["id"]
                await asyncio.sleep(1)
        except (WebSocketDisconnect, HTTPException, ValueError, TimeoutError, SQLAlchemyError):
            try:
                await ws.close(code=1008)
            except RuntimeError:
                pass

    return app
