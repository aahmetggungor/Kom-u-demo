"""PII-free, low-cardinality worker metrics for an optional local endpoint."""

from datetime import UTC, datetime

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server
from sqlalchemy import func, select

from .db import tenant_session
from .models import Job, Report


class WorkerMetrics:
    def __init__(self, port: int | None = None):
        self.registry = CollectorRegistry()
        self.jobs = Counter(
            "komsu_worker_jobs_total",
            "Final worker outcomes",
            ["result"],
            registry=self.registry,
        )
        self.analysis_seconds = Histogram(
            "komsu_worker_analysis_duration_seconds",
            "Analyzer pipeline time outside database locks",
            registry=self.registry,
        )
        self.job_seconds = Histogram(
            "komsu_worker_job_duration_seconds",
            "Claim through committed result duration",
            registry=self.registry,
        )
        self.queue_wait_seconds = Histogram(
            "komsu_worker_queue_wait_seconds",
            "Report creation to worker claim delay",
            registry=self.registry,
        )
        self.queue_depth = Gauge(
            "komsu_worker_queue_depth",
            "Jobs currently visible to this tenant worker",
            ["state"],
            registry=self.registry,
        )
        self.oldest_seconds = Gauge(
            "komsu_worker_oldest_pending_seconds",
            "Age of the oldest queued or running report",
            registry=self.registry,
        )
        self._server = (
            start_http_server(port, addr="127.0.0.1", registry=self.registry) if port else None
        )

    def observe(self, result: str, total_seconds: float, analysis_seconds: float, wait: float):
        if result not in {"done", "retry", "failed", "stale"}:
            raise ValueError("Unsupported worker metric result")
        self.jobs.labels(result).inc()
        self.job_seconds.observe(max(0.0, total_seconds))
        self.analysis_seconds.observe(max(0.0, analysis_seconds))
        self.queue_wait_seconds.observe(max(0.0, wait))

    def snapshot(self, engine, tenant_id: str):
        with tenant_session(engine, tenant_id) as session:
            counts = dict(
                session.execute(
                    select(Job.state, func.count())
                    .where(Job.tenant_id == tenant_id, Job.state.in_(["QUEUED", "RUNNING"]))
                    .group_by(Job.state)
                ).all()
            )
            oldest = session.scalar(
                select(func.min(Report.created_at))
                .join(Job, (Job.tenant_id == Report.tenant_id) & (Job.report_id == Report.id))
                .where(Job.tenant_id == tenant_id, Job.state.in_(["QUEUED", "RUNNING"]))
            )
        for state in ("QUEUED", "RUNNING"):
            self.queue_depth.labels(state.lower()).set(counts.get(state, 0))
        if oldest is None:
            self.oldest_seconds.set(0)
        else:
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=UTC)
            self.oldest_seconds.set(max(0.0, (datetime.now(UTC) - oldest).total_seconds()))


class EmbeddingMetrics:
    def __init__(self, port: int | None = None):
        self.registry = CollectorRegistry()
        self.batches = Counter(
            "komsu_embedding_batches_total",
            "Local embedding batch outcomes",
            ["result"],
            registry=self.registry,
        )
        self.reports = Counter(
            "komsu_embedding_reports_total",
            "Reports committed with the configured embedding revision",
            registry=self.registry,
        )
        self.seconds = Histogram(
            "komsu_embedding_batch_duration_seconds",
            "Local model encoding plus vector commit duration",
            registry=self.registry,
        )
        self.pending = Gauge(
            "komsu_embedding_pending_reports",
            "Pending reports observed in the latest bounded query",
            registry=self.registry,
        )
        self._server = (
            start_http_server(port, addr="127.0.0.1", registry=self.registry) if port else None
        )

    def observe_batch(self, result: str, reports: int, seconds: float):
        if result not in {"done", "database_error", "model_error"}:
            raise ValueError("Unsupported embedding metric result")
        self.batches.labels(result).inc()
        self.seconds.observe(max(0.0, seconds))
        if result == "done":
            self.reports.inc(max(0, reports))
