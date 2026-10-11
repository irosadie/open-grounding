"""Bounded structured metrics for RAG query stages without query or source content."""

import json
import logging

logger = logging.getLogger("rag_metrics")

_MAX_REASON_LENGTH = 96
_MAX_KNOWLEDGE_BASE_COUNT = 1000


def record_query_metric(*, tenant_id: str, trace_id: str, stage: str, outcome: str, duration_ms: int) -> None:
    logger.info(
        json.dumps(
            {
                "metric": "rag_query_stage",
                "tenantId": tenant_id,
                "traceId": trace_id,
                "stage": stage,
                "outcome": outcome,
                "durationMs": max(0, duration_ms),
            }
        )
    )


def record_project_metric(
    *,
    tenant_id: str,
    metric: str,
    outcome: str,
    project_id: str | None = None,
    knowledge_base_count: int | None = None,
    reason_code: str | None = None,
) -> None:
    """Emit bounded Project lifecycle/scope telemetry without user content."""

    payload: dict[str, object] = {
        "metric": f"rag_project_{metric}",
        "tenantId": tenant_id,
        "outcome": outcome,
    }
    if project_id is not None:
        payload["projectId"] = project_id
    if knowledge_base_count is not None:
        payload["knowledgeBaseCount"] = min(max(0, knowledge_base_count), _MAX_KNOWLEDGE_BASE_COUNT)
    if reason_code is not None:
        payload["reasonCode"] = reason_code[:_MAX_REASON_LENGTH]
    logger.info(json.dumps(payload))


def _emit_trace(event: str, **meta: object) -> None:
    """Best-effort dev-trace mirror; never raises from metric paths."""
    try:
        from app.core.dev_trace import get_tracer

        get_tracer().emit(event, **meta)  # type: ignore[arg-type]
    except Exception:
        pass


def record_qdrant_timing(*, tenant_id: str, trace_id: str, duration_ms: int, outcome: str = "ok") -> None:
    """Lightweight Qdrant query timing (qdrant_ms) without payload content."""
    bounded = max(0, duration_ms)
    logger.info(
        json.dumps(
            {
                "metric": "rag_qdrant_query",
                "tenantId": tenant_id,
                "traceId": trace_id,
                "stage": "qdrant",
                "outcome": outcome[:_MAX_REASON_LENGTH],
                "durationMs": bounded,
                "qdrantMs": bounded,
            }
        )
    )
    _emit_trace("retrieval.qdrant", tenant_id=tenant_id, trace_id=trace_id, qdrant_ms=bounded, outcome=outcome)


def record_embed_timing(*, tenant_id: str, trace_id: str, duration_ms: int, outcome: str = "ok") -> None:
    """Lightweight embedding timing (embed_ms) without query text."""
    bounded = max(0, duration_ms)
    logger.info(
        json.dumps(
            {
                "metric": "rag_embed",
                "tenantId": tenant_id,
                "traceId": trace_id,
                "stage": "embed",
                "outcome": outcome[:_MAX_REASON_LENGTH],
                "durationMs": bounded,
                "embedMs": bounded,
            }
        )
    )
    _emit_trace("retrieval.embed", tenant_id=tenant_id, trace_id=trace_id, embed_ms=bounded, outcome=outcome)


def record_db_pool_wait(*, tenant_id: str, trace_id: str, duration_ms: int, outcome: str = "ok") -> None:
    """Lightweight DB pool-wait timing without query content."""
    bounded = max(0, duration_ms)
    logger.info(
        json.dumps(
            {
                "metric": "rag_db_pool_wait",
                "tenantId": tenant_id,
                "traceId": trace_id,
                "stage": "db_pool",
                "outcome": outcome[:_MAX_REASON_LENGTH],
                "durationMs": bounded,
            }
        )
    )
    _emit_trace("db.pool_wait", tenant_id=tenant_id, trace_id=trace_id, db_pool_wait_ms=bounded, outcome=outcome)


def record_trace_async_fail(*, tenant_id: str, trace_id: str, reason: str, stage: str = "trace") -> None:
    """Counter for async trace-emit failures; bounded reason, no user content."""
    logger.info(
        json.dumps(
            {
                "metric": "rag_trace_async_fail",
                "tenantId": tenant_id,
                "traceId": trace_id,
                "stage": stage[:_MAX_REASON_LENGTH],
                "outcome": "failed",
                "reason": reason[:_MAX_REASON_LENGTH],
            }
        )
    )
