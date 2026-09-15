import json
import logging
import time
from datetime import UTC, timedelta

from sqlalchemy import and_, or_, select, update

from .ai import Analyzer, BaselineAnalyzer
from .db import tenant_session
from .domain import emit, serialize_tenant
from .models import Case, Job, Report, uid, utcnow
from .pipeline import ValidatedAnalysis

logger = logging.getLogger("komsu.worker")


def process_one(engine, tenant_id: str, analyzer: Analyzer | None = None, metrics=None) -> bool:
    analyzer = analyzer or BaselineAnalyzer()
    job_started = time.monotonic()
    now = utcnow()
    claim = uid()
    with tenant_session(engine, tenant_id) as session:
        job = session.scalar(
            select(Job)
            .where(
                Job.tenant_id == tenant_id,
                or_(
                    and_(Job.state == "QUEUED", Job.available_at <= now),
                    and_(Job.state == "RUNNING", Job.lease_until < now),
                ),
            )
            .order_by(Job.available_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        # SQL predicate also protects competing SQLite test workers; PostgreSQL uses row lock.
        changed = session.execute(
            update(Job)
            .where(
                Job.id == job.id,
                Job.tenant_id == tenant_id,
                or_(Job.state == "QUEUED", Job.lease_until < now),
            )
            .values(
                state="RUNNING",
                claim_id=claim,
                lease_until=now + timedelta(seconds=120),
                attempts=Job.attempts + 1,
            )
            .execution_options(synchronize_session="fetch")
        )
        if changed.rowcount != 1:
            session.rollback()
            return False
        report = session.scalar(
            select(Report).where(Report.tenant_id == tenant_id, Report.id == job.report_id)
        )
        job_id, report_id = job.id, report.id
        input_data = (report.original_text, report.original_language, report.address_raw)
        created_at = report.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        session.commit()
    # Expensive model work runs outside transaction/locks. No autonomous dispatch path.
    analysis_started = time.monotonic()
    try:
        analysis = ValidatedAnalysis.model_validate(analyzer.analyze(*input_data)).model_dump()
        error = None
    except Exception:
        analysis = None
        error = "ANALYZER_FAILURE"  # Never log model exception text containing source data.
    analysis_seconds = time.monotonic() - analysis_started
    with tenant_session(engine, tenant_id) as session:
        serialize_tenant(session, tenant_id)
        job = session.scalar(
            select(Job).where(Job.tenant_id == tenant_id, Job.id == job_id).with_for_update()
        )
        if job.claim_id != claim or job.state != "RUNNING":
            if metrics:
                metrics.observe(
                    "stale",
                    time.monotonic() - job_started,
                    analysis_seconds,
                    max(0.0, (now - created_at).total_seconds()),
                )
            return True  # A newer lease owns the job; discard stale result.
        report = session.scalar(
            select(Report).where(Report.tenant_id == tenant_id, Report.id == report_id)
        )
        case = session.scalar(
            select(Case).where(Case.tenant_id == tenant_id, Case.id == report.case_id)
        )
        if error:
            job.last_error = error
            job.state = "FAILED" if job.attempts >= 3 else "QUEUED"
            job.available_at = utcnow() + timedelta(seconds=2**job.attempts)
            report.processing_status = job.state
            report.analysis = {"warnings": [error], "human_review_required": True}
        else:
            report.analysis = analysis
            report.processing_status = "PROCESSED"
            report.original_language = analysis["original_language"]
            # Do not overwrite ANY human-reviewed priority or verified/dispatched state.
            if case.version == 1 and case.status == "OPEN":
                case.needs = analysis["needs"]
                case.urgency_level = analysis["urgency_level"]
                case.incident_type = analysis["incident_type"]
                case.ai_confidence = analysis["ai_confidence"]
                if report.reported_lat is not None and report.reported_lon is not None:
                    case.lat, case.lon = report.reported_lat, report.reported_lon
                    case.location_status = "UNCONFIRMED"
            job.state = "DONE"
            job.last_error = None
        job.claim_id = None
        job.lease_until = None
        case.version += 1
        case.updated_at = utcnow()
        emit(session, case, "case.analysis_updated")
        attempt_count = job.attempts
        session.commit()
    outcome = "done" if error is None else "failed" if attempt_count >= 3 else "retry"
    if metrics:
        metrics.observe(
            outcome,
            time.monotonic() - job_started,
            analysis_seconds,
            max(0.0, (now - created_at).total_seconds()),
        )
    logger.info(
        json.dumps(
            {
                "event": "worker_job_completed",
                "result": outcome,
                "attempt": attempt_count,
                "duration_ms": round((time.monotonic() - job_started) * 1000, 3),
            }
        )
    )
    return True


def run(engine, tenant_id: str):
    from .config import Settings
    from .geolocation import NominatimSelfHosted
    from .pipeline import Pipeline
    from .worker_observability import WorkerMetrics

    settings = Settings()
    translator = None
    if settings.translation_model_dir:
        from .translation import LocalMarianTranslator

        translator = LocalMarianTranslator(settings.translation_model_dir)
    pipeline = Pipeline(
        tenant_id,
        geocoder=NominatimSelfHosted(settings.geocoder_url) if settings.geocoder_url else None,
        translator=translator,
    )
    metrics = WorkerMetrics(settings.worker_metrics_port)
    last_snapshot = 0.0
    while True:
        now = time.monotonic()
        if now - last_snapshot >= 5:
            metrics.snapshot(engine, tenant_id)
            last_snapshot = now
        if not process_one(engine, tenant_id, pipeline, metrics):
            time.sleep(1)
