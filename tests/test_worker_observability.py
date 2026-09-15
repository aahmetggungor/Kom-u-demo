from datetime import UTC, datetime
from uuid import uuid4

import pytest
from conftest import headers
from komsu.worker import process_one
from komsu.worker_observability import EmbeddingMetrics, WorkerMetrics
from prometheus_client import generate_latest


def report():
    return {
        "client_id": str(uuid4()),
        "source": "manual",
        "language": "en",
        "text": "Synthetic: three people need water",
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def test_worker_emits_fixed_result_and_latency_metrics(setup):
    engine, client, actor, *_ = setup
    assert client.post("/api/v1/reports", headers=headers(actor), json=report()).status_code == 202
    metrics = WorkerMetrics()
    assert process_one(engine, actor["tenant_id"], metrics=metrics)
    output = generate_latest(metrics.registry).decode()
    assert 'komsu_worker_jobs_total{result="done"} 1.0' in output
    assert "komsu_worker_analysis_duration_seconds_count 1.0" in output
    assert "komsu_worker_queue_wait_seconds_count 1.0" in output


def test_queue_snapshot_has_no_tenant_or_report_labels(setup):
    engine, client, actor, *_ = setup
    assert client.post("/api/v1/reports", headers=headers(actor), json=report()).status_code == 202
    metrics = WorkerMetrics()
    metrics.snapshot(engine, actor["tenant_id"])
    output = generate_latest(metrics.registry).decode()
    assert 'komsu_worker_queue_depth{state="queued"} 1.0' in output
    assert actor["tenant_id"] not in output
    with pytest.raises(ValueError):
        metrics.observe("arbitrary-label", 0, 0, 0)


def test_embedding_metrics_have_fixed_labels_and_no_revision():
    metrics = EmbeddingMetrics()
    metrics.pending.set(4)
    metrics.observe_batch("done", 4, 0.5)
    output = generate_latest(metrics.registry).decode()
    assert 'komsu_embedding_batches_total{result="done"} 1.0' in output
    assert "komsu_embedding_reports_total 4.0" in output
    assert "komsu_embedding_pending_reports 4.0" in output
    with pytest.raises(ValueError):
        metrics.observe_batch("revision-or-exception-label", 0, 0)
