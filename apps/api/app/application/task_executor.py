"""Concurrent execution of typed query tasks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from app.domain.rag.task_plan import TaskResult, TaskSpec, TaskType

TaskHandler = Callable[[TaskSpec], Awaitable[object]]


class TaskExecutor:
    def __init__(
        self,
        *,
        rag_handler: TaskHandler,
        general_handler: TaskHandler,
        mcp_handler: TaskHandler | None = None,
        mcp_enabled: bool = False,
        task_timeout_seconds: int = 15,
    ) -> None:
        self._handlers = {
            TaskType.RAG: rag_handler,
            TaskType.GENERAL: general_handler,
        }
        self._mcp_handler = mcp_handler
        self._mcp_enabled = mcp_enabled
        self._timeout = task_timeout_seconds

    async def execute(self, tasks: tuple[TaskSpec, ...] | list[TaskSpec]) -> list[TaskResult]:
        results = await asyncio.gather(*(self._execute_one(task) for task in tasks), return_exceptions=True)
        return [result if isinstance(result, TaskResult) else self._unexpected_result(task, result) for task, result in zip(tasks, results, strict=True)]

    async def _execute_one(self, task: TaskSpec) -> TaskResult:
        started = time.monotonic()
        if task.type is TaskType.MCP and (not self._mcp_enabled or self._mcp_handler is None):
            return self._result(task, started, status="skipped", error="capability_not_enabled")
        handler = self._mcp_handler if task.type is TaskType.MCP else self._handlers.get(task.type)
        if handler is None:
            return self._result(task, started, status="denied", error="unsupported_task_type")
        try:
            async with asyncio.timeout(self._timeout):
                payload = await handler(task)
            return self._result(task, started, status="success", payload=payload)
        except asyncio.TimeoutError:
            return self._result(task, started, status="timeout", error="task_timeout")
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "TOOL_DENIED":
                return self._result(task, started, status="denied", error="tool_denied")
            if code == "TOOL_TIMEOUT":
                return self._result(task, started, status="timeout", error="tool_timeout")
            return self._result(task, started, status="error", error=type(exc).__name__)

    def _result(self, task: TaskSpec, started: float, *, status: str, error: str | None = None, payload: object = None) -> TaskResult:
        duration_ms = int((time.monotonic() - started) * 1000)
        if task.type is TaskType.RAG:
            return TaskResult(task.id, task.type, status, error, duration_ms, rag=payload if isinstance(payload, list) else None)
        if task.type is TaskType.MCP:
            return TaskResult(task.id, task.type, status, error, duration_ms, mcp=payload if isinstance(payload, dict) else None)
        return TaskResult(task.id, task.type, status, error, duration_ms, general=payload if isinstance(payload, str) else None)

    def _unexpected_result(self, task: TaskSpec, error: BaseException) -> TaskResult:
        return TaskResult(task.id, task.type, "error", type(error).__name__)
