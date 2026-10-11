from datetime import UTC, datetime, timedelta

from app.application.task_resumer import TaskResumer
from app.domain.rag.task_plan import TaskResult, TaskType


def test_resumer_merges_evidence_and_labels_supplementary_context() -> None:
    result = TaskResumer().resume([
        TaskResult("r1", TaskType.RAG, "success", rag=[{"id": "a", "score": 0.8, "source": "doc"}]),
        TaskResult("g1", TaskType.GENERAL, "success", general="context"),
    ], top_k=5)
    assert len(result.evidence) == 1
    assert "[Related context:]" in result.supplementary_context
    assert result.route == "grounded"


def test_resumer_abstains_without_successful_outputs() -> None:
    result = TaskResumer().resume([TaskResult("r1", TaskType.RAG, "error")], top_k=5)
    assert result.route == "abstain"


def test_resumer_converts_successful_mcp_result_to_bounded_provenance() -> None:
    result = TaskResumer().resume([
        TaskResult(
            "mcp-1",
            TaskType.MCP,
            "success",
            mcp={
                "result": {"value": "live"},
                "provenance": {
                    "sourceKind": "MCP",
                    "tenantId": "tenant-1",
                    "serverId": "server-1",
                    "toolId": "tool-1",
                    "invocationId": "inv-1",
                    "traceId": "trace-1",
                    "producedAt": datetime.now(UTC).isoformat(),
                    "expiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
                },
            },
        )
    ], top_k=5)

    assert result.route == "grounded"
    assert result.mcp_provenance[0]["citationId"] == "M1"
    assert result.mcp_provenance[0]["tenantId"] == "tenant-1"
    assert "untrusted source data" in result.supplementary_context
