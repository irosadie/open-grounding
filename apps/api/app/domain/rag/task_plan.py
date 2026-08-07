"""Typed task plans produced by the RAG query planner."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


class TaskType(StrEnum):
    RAG = "RAG"
    MCP = "MCP"
    GENERAL = "GENERAL"


@dataclass(frozen=True)
class TaskSpec:
    id: str
    type: TaskType
    intent: str
    query: str | None = None
    knowledge_base_ids: tuple[str, ...] = ()
    refs: tuple[str, ...] = ()
    tool_ref: str | None = None
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPlan:
    tasks: tuple[TaskSpec, ...]
    truncated: bool = False
    fallback: bool = False
    fallback_reason: str | None = None


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    task_type: TaskType
    status: str
    error: str | None = None
    duration_ms: int = 0
    rag: list[dict[str, object]] | None = None
    mcp: dict[str, object] | None = None
    general: str | None = None


@dataclass(frozen=True)
class ResumeResult:
    evidence: tuple[dict[str, object], ...]
    supplementary_context: str
    route: str
    dedup_removed: int = 0
    supplementary_blocks: int = 0


def parse_task_plan(
    raw_json: str,
    max_tasks: int,
    allowed_types: set[TaskType | str] | tuple[TaskType | str, ...] | None = None,
) -> TaskPlan:
    """Parse and validate the planner's JSON array, truncating excess tasks."""
    if not 1 <= max_tasks <= 8:
        raise ValueError("max_tasks must be between 1 and 8")

    raw = raw_json.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array of tasks")

    try:
        allowed = {TaskType(value) for value in (allowed_types or tuple(TaskType))}
    except ValueError as exc:
        raise ValueError("allowed_types contains an unsupported task type") from exc
    tasks: list[TaskSpec] = []
    for index, item in enumerate(parsed, start=1):
        if not isinstance(item, Mapping):
            raise ValueError("Each task must be an object")
        try:
            task_type = TaskType(str(item["type"]).upper())
            if task_type not in allowed:
                raise ValueError(f"Task type {task_type} is not allowed")
            task_id = str(item.get("id", f"t{index}")).strip()
            intent = str(item["intent"]).strip()
            if not task_id or not intent:
                raise ValueError("Task id and intent are required")
            query = item.get("query")
            if query is not None:
                query = str(query).strip() or None
            knowledge_base_ids = tuple(str(value) for value in item.get("knowledge_base_ids", ()))
            refs = tuple(str(value) for value in item.get("refs", ()))
            arguments = item.get("arguments", {})
            if not isinstance(arguments, Mapping):
                raise ValueError("MCP arguments must be an object")
            if task_type in (TaskType.RAG, TaskType.GENERAL) and not query:
                raise ValueError(f"{task_type} tasks require query")
            if task_type is TaskType.MCP and not str(item.get("tool_ref", "")).strip():
                raise ValueError("MCP tasks require tool_ref")
        except (KeyError, TypeError) as exc:
            raise ValueError("Invalid task object") from exc
        tasks.append(
            TaskSpec(
                id=task_id,
                type=task_type,
                intent=intent,
                query=query,
                knowledge_base_ids=knowledge_base_ids,
                refs=refs,
                tool_ref=str(item.get("tool_ref")).strip() if item.get("tool_ref") else None,
                arguments=dict(arguments),
            )
        )

    if not tasks:
        raise ValueError("Task plan must contain at least one task")
    return TaskPlan(tasks=tuple(tasks[:max_tasks]), truncated=len(tasks) > max_tasks)


def fallback_task_plan(query: str, reason: str) -> TaskPlan:
    return TaskPlan(
        tasks=(TaskSpec(id="t1", type=TaskType.RAG, intent="retrieve_evidence", query=query),),
        fallback=True,
        fallback_reason=reason,
    )
