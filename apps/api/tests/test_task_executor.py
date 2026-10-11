import asyncio

import pytest

from app.application.task_executor import TaskExecutor
from app.domain.models import PolicyScope
from app.domain.rag.answer_policy import GuardrailProfile
from app.domain.rag.task_plan import TaskSpec, TaskType


@pytest.mark.asyncio
async def test_tasks_run_in_parallel_and_isolate_errors() -> None:
    async def rag(_: TaskSpec) -> list[dict[str, object]]:
        await asyncio.sleep(0.01)
        return [{"id": "chunk", "score": 0.9}]

    async def general(_: TaskSpec) -> str:
        raise ValueError("failed")

    results = await TaskExecutor(rag_handler=rag, general_handler=general).execute([
        TaskSpec("rag", TaskType.RAG, "retrieve", query="q"),
        TaskSpec("general", TaskType.GENERAL, "answer", query="q"),
    ])
    assert [result.status for result in results] == ["success", "error"]


@pytest.mark.asyncio
async def test_timeout_does_not_cancel_other_task() -> None:
    async def rag(_: TaskSpec) -> list[dict[str, object]]:
        await asyncio.sleep(0.01)
        return []

    async def general(_: TaskSpec) -> str:
        await asyncio.sleep(0.1)
        return "late"

    results = await TaskExecutor(rag_handler=rag, general_handler=general, task_timeout_seconds=0.02).execute([
        TaskSpec("rag", TaskType.RAG, "retrieve", query="q"),
        TaskSpec("general", TaskType.GENERAL, "answer", query="q"),
    ])
    assert [result.status for result in results] == ["success", "timeout"]


@pytest.mark.asyncio
async def test_mcp_task_is_skipped_without_capability() -> None:
    async def noop(_: TaskSpec) -> str:
        return "unused"

    results = await TaskExecutor(rag_handler=noop, general_handler=noop).execute([
        TaskSpec("mcp", TaskType.MCP, "lookup", tool_ref="server:tool"),
    ])
    assert results[0].status == "skipped"
    assert results[0].error == "capability_not_enabled"


@pytest.mark.asyncio
async def test_dependent_task_waits_and_receives_prerequisite_context() -> None:
    started: list[str] = []
    child_queries: list[str] = []

    async def rag(task: TaskSpec) -> list[dict[str, object]]:
        started.append(task.id)
        if task.id == "a":
            await asyncio.sleep(0.01)
            return [{"id": "chunk-a", "text": "result from A"}]
        child_queries.append(task.query or "")
        return []

    results = await TaskExecutor(rag_handler=rag, general_handler=rag).execute([
        TaskSpec("a", TaskType.RAG, "first", query="question A"),
        TaskSpec("b", TaskType.RAG, "second", query="question B", depends_on=("a",)),
    ])

    assert started == ["a", "b"]
    assert "result from A" in child_queries[0]
    assert results[1].dependency_ids == ("a",)
    assert results[1].dependency_context_chars > 0


@pytest.mark.asyncio
async def test_dependency_failure_skips_only_dependents() -> None:
    async def rag(task: TaskSpec) -> list[dict[str, object]]:
        if task.id == "a":
            raise ValueError("failed")
        return []

    results = await TaskExecutor(rag_handler=rag, general_handler=rag).execute([
        TaskSpec("a", TaskType.RAG, "first", query="question A"),
        TaskSpec("b", TaskType.RAG, "second", query="question B", depends_on=("a",)),
        TaskSpec("c", TaskType.RAG, "independent", query="question C"),
    ])

    assert [result.status for result in results] == ["error", "skipped", "success"]
    assert results[1].error == "dependency_failed"


@pytest.mark.asyncio
async def test_dependency_context_is_bounded() -> None:
    child_queries: list[str] = []

    async def rag(task: TaskSpec) -> list[dict[str, object]]:
        if task.id == "a":
            return [{"text": "x" * 500}]
        child_queries.append(task.query or "")
        return []

    results = await TaskExecutor(rag_handler=rag, general_handler=rag, dependency_context_max_chars=80).execute([
        TaskSpec("a", TaskType.RAG, "first", query="question A"),
        TaskSpec("b", TaskType.RAG, "second", query="question B", depends_on=("a",)),
    ])

    assert results[1].dependency_context_chars <= 80
    assert "dependency context truncated" in child_queries[0]


@pytest.mark.asyncio
async def test_mcp_guardrails_bound_calls_and_payload_before_handler() -> None:
    calls: list[str] = []

    async def mcp(task: TaskSpec) -> str:
        calls.append(task.id)
        return "ok"

    policy = GuardrailProfile(
        version="test",
        scope=PolicyScope.KNOWLEDGE_BASE,
        max_tool_calls=1,
        max_tool_payload_bytes=65_536,
    )
    results = await TaskExecutor(
        rag_handler=mcp,
        general_handler=mcp,
        mcp_handler=mcp,
        mcp_enabled=True,
        guardrails=policy,
    ).execute([
        TaskSpec("oversized", TaskType.MCP, "lookup", tool_ref="tool", arguments={"value": "x" * 70_000}),
        TaskSpec("first", TaskType.MCP, "lookup", tool_ref="tool", arguments={"value": "x"}),
        TaskSpec("second", TaskType.MCP, "lookup", tool_ref="tool", arguments={"value": "x"}),
    ])

    assert len(calls) == 1
    assert sum(result.status == "success" for result in results) == 1
    assert any(result.error == "tool_call_limit_exceeded" for result in results)
    assert any(result.error == "tool_payload_limit_exceeded" for result in results)


@pytest.mark.asyncio
async def test_mcp_guardrails_require_confirmation_fail_closed() -> None:
    async def mcp(_: TaskSpec) -> str:
        raise AssertionError("handler must not run")

    policy = GuardrailProfile(
        version="test",
        scope=PolicyScope.KNOWLEDGE_BASE,
        require_tool_confirmation=True,
    )
    result = await TaskExecutor(
        rag_handler=mcp,
        general_handler=mcp,
        mcp_handler=mcp,
        mcp_enabled=True,
        guardrails=policy,
    ).execute([TaskSpec("mcp", TaskType.MCP, "lookup", tool_ref="tool")])

    assert result[0].status == "denied"
    assert result[0].error == "tool_confirmation_required"
