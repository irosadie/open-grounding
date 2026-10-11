"""Typed task plans produced by the RAG query planner."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


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
    depends_on: tuple[str, ...] = ()
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
    dependency_ids: tuple[str, ...] = ()
    dependency_context_chars: int = 0


@dataclass(frozen=True)
class ResumeResult:
    evidence: tuple[dict[str, object], ...]
    supplementary_context: str
    route: str
    dedup_removed: int = 0
    supplementary_blocks: int = 0
    mcp_provenance: tuple[dict[str, object], ...] = ()


def parse_task_plan(
    raw_json: str,
    max_tasks: int,
    allowed_types: set[TaskType | str] | tuple[TaskType | str, ...] | None = None,
    max_depth: int = 2,
) -> TaskPlan:
    """Parse and validate the planner's JSON array, truncating excess tasks."""
    if not 1 <= max_tasks <= 8:
        raise ValueError("max_tasks must be between 1 and 8")
    if not 1 <= max_depth <= 2:
        raise ValueError("max_depth must be between 1 and 2")

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
            raise ValueError(f"Task at index {index} must be an object, got {type(item).__name__}")
        try:
            task_type = TaskType(str(item["type"]).upper())
            if task_type not in allowed:
                raise ValueError(f"Task type {task_type} is not allowed (allowed: {', '.join(t.value for t in allowed)})")
            task_id = str(item.get("id", f"t{index}")).strip()
            intent = str(item["intent"]).strip()
            if not task_id or not intent:
                raise ValueError("Task id and intent must be non-empty strings")
            query = item.get("query")
            if query is not None:
                query = str(query).strip() or None
            knowledge_base_ids = tuple(str(value) for value in item.get("knowledge_base_ids", ()))
            raw_dependencies = item.get("depends_on", item.get("dependsOn", item.get("refs", ())))
            if raw_dependencies is None:
                raw_dependencies = ()
            if isinstance(raw_dependencies, (str, bytes)) or not isinstance(raw_dependencies, (list, tuple, set)):
                raise ValueError("depends_on must be an array of task IDs")
            depends_on = tuple(str(value).strip() for value in raw_dependencies)
            if any(not dependency for dependency in depends_on):
                raise ValueError("depends_on task IDs must be non-empty strings")
            if len(set(depends_on)) != len(depends_on):
                raise ValueError("depends_on must not contain duplicate task IDs")
            arguments = item.get("arguments", {})
            if not isinstance(arguments, Mapping):
                raise ValueError("MCP arguments must be an object")
            if task_type in (TaskType.RAG, TaskType.GENERAL) and not query:
                raise ValueError(f"{task_type} tasks require a non-empty 'query' field")
            if task_type is TaskType.MCP and not str(item.get("tool_ref", "")).strip():
                raise ValueError("MCP tasks require a non-empty 'tool_ref' field")
        except (KeyError, TypeError) as exc:
            missing = str(exc).strip("'")
            raise ValueError(f"Task at index {index} is missing required field: {missing}") from exc
        tasks.append(
            TaskSpec(
                id=task_id,
                type=task_type,
                intent=intent,
                query=query,
                knowledge_base_ids=knowledge_base_ids,
                refs=depends_on,
                depends_on=depends_on,
                tool_ref=str(item.get("tool_ref")).strip() if item.get("tool_ref") else None,
                arguments=dict(arguments),
            )
        )

    if not tasks:
        raise ValueError("Task plan must contain at least one task")
    selected_tasks = tuple(tasks[:max_tasks])
    validate_task_dependencies(selected_tasks, max_depth=max_depth)
    return TaskPlan(tasks=selected_tasks, truncated=len(tasks) > max_tasks)


def task_dependencies(task: TaskSpec) -> tuple[str, ...]:
    """Return the canonical dependency IDs, including legacy ``refs`` plans."""
    return task.depends_on or task.refs


def validate_task_dependencies(tasks: tuple[TaskSpec, ...] | list[TaskSpec], *, max_depth: int = 2) -> None:
    """Validate a bounded dependency graph before any task is executed."""
    if not 1 <= max_depth <= 2:
        raise ValueError("max_depth must be between 1 and 2")

    task_by_id: dict[str, TaskSpec] = {}
    for task in tasks:
        if not task.id or task.id in task_by_id:
            raise ValueError(f"Task IDs must be unique and non-empty: {task.id!r}")
        task_by_id[task.id] = task

    for task in tasks:
        dependencies = task_dependencies(task)
        if task.type is TaskType.MCP and dependencies:
            raise ValueError("MCP tasks cannot declare dependencies")
        for dependency in dependencies:
            if dependency == task.id:
                raise ValueError(f"Task {task.id!r} cannot depend on itself")
            if dependency not in task_by_id:
                raise ValueError(f"Task {task.id!r} references unknown dependency {dependency!r}")

    depths: dict[str, int] = {}

    def resolve_depth(task_id: str, visiting: set[str]) -> int:
        if task_id in depths:
            return depths[task_id]
        if task_id in visiting:
            raise ValueError("Task dependencies must be acyclic")
        visiting.add(task_id)
        task = task_by_id[task_id]
        dependencies = task_dependencies(task)
        depth = 1 if not dependencies else 1 + max(resolve_depth(dependency, visiting) for dependency in dependencies)
        visiting.remove(task_id)
        if depth > max_depth:
            raise ValueError(f"Task dependency depth exceeds maximum of {max_depth}")
        depths[task_id] = depth
        return depth

    for task in tasks:
        resolve_depth(task.id, set())


def fallback_task_plan(
    query: str,
    reason: str,
    allowed_types: set[TaskType | str] | None = None,
) -> TaskPlan:
    allowed = {TaskType(t) for t in (allowed_types or {TaskType.RAG})} if allowed_types else {TaskType.RAG}
    fallback_type = (
        TaskType.RAG if TaskType.RAG in allowed
        else TaskType.GENERAL if TaskType.GENERAL in allowed
        else next(iter(allowed), TaskType.RAG)
    )
    return TaskPlan(
        tasks=(TaskSpec(id="t1", type=fallback_type, intent="retrieve_evidence", query=query),),
        fallback=True,
        fallback_reason=reason,
    )
