# Observability boundary — 2026-09-15

Embedding polling accepts `--metrics-port 9102` and binds to loopback. It exposes `komsu_embedding_batches_total` with fixed `done`, `database_error`, `model_error` labels; `komsu_embedding_reports_total`; `komsu_embedding_batch_duration_seconds`; and `komsu_embedding_pending_reports`. A batch is at most four reports. The report counter increments after commit and counts actual inserts, so earlier commits survive a later failure and conflict replays add zero. Pending reports describes the latest bounded query, capped by `--limit`, rather than total backlog. Model loading/polling errors are outside batch metrics. Counters reset on restart. PostgreSQL tests cover partial failure and replay accounting. CLI errors omit exception details that could contain source data.

The API exposes Prometheus text at `/metrics` only after application-level admin authentication. It currently reports HTTP count by method/status and a duration histogram. It does not label tenant, route parameters, tokens, headers or report content.

The per-tenant worker optionally starts a loopback-only Prometheus server when `KOMSU_WORKER_METRICS_PORT` is set. Leaving the variable empty opens no port. Available series are:

- `komsu_worker_jobs_total{result=done|retry|failed|stale}`
- `komsu_worker_analysis_duration_seconds`
- `komsu_worker_job_duration_seconds`
- `komsu_worker_queue_wait_seconds`
- `komsu_worker_queue_depth{state=queued|running}`
- `komsu_worker_oldest_pending_seconds`

Labels are fixed in code and reject arbitrary results. No tenant/report/case/model revision or warning string enters a label. The structured completion log contains only event name, fixed result, attempt number and duration; it does not contain identifiers or source text. Database exceptions and model exceptions remain generic.

Example local run:

```powershell
$env:KOMSU_WORKER_METRICS_PORT='9101'
python -m komsu.cli worker --tenant TENANT_UUID
curl http://127.0.0.1:9101/metrics
```

This is instrumentation, not an operating monitoring system. There is no deployed scraper, durable metric store, dashboard, alert routing, trace context, OTLP exporter or runbook-tested on-call path. Alert thresholds must be derived from an approved load/capacity exercise; arbitrary queue-age thresholds could create false confidence. A future scrape configuration must keep this endpoint on a management network or authenticated proxy and retain low-cardinality labels.
