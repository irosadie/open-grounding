"""Bounded structured metrics for RAG query stages without query or source content."""

import json
import logging

logger = logging.getLogger("rag_metrics")


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
