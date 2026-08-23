import asyncio

import pytest

from app.application.task_executor import TaskExecutor
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
