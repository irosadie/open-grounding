from time import monotonic

from app.application.rag_query_service import _duration_ms, _record_safe_pipeline_metrics


def test_query_metric_duration_is_bounded_to_zero_or_greater() -> None:
    assert _duration_ms(monotonic()) >= 0


def test_safe_pipeline_metrics_record_unexecuted_stages_explicitly(monkeypatch) -> None:
    metrics: list[tuple[str, str]] = []

    def capture_metric(*, stage: str, outcome: str, **_: object) -> None:
        metrics.append((stage, outcome))

    monkeypatch.setattr("app.application.rag_query_service.record_query_metric", capture_metric)
    _record_safe_pipeline_metrics(tenant_id="tenant-1", trace_id="trace-1", route="abstain", duration_ms=1)

    assert metrics == [
        ("planning", "abstain"),
        ("retrieval", "skipped"),
        ("reranking", "skipped"),
        ("generation", "skipped"),
        ("validation", "safe_abstention"),
    ]
