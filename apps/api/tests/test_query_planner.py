import json

import pytest

from app.domain.rag.task_plan import TaskType, fallback_task_plan, parse_task_plan


def _task(task_id: str, task_type: str = "RAG", depends_on: list[str] | None = None) -> dict[str, object]:
    task: dict[str, object] = {"id": task_id, "type": task_type, "intent": "answer", "query": "test"}
    if depends_on is not None:
        task["depends_on"] = depends_on
    if task_type == "MCP":
        task["tool_ref"] = "server:tool"
        task.pop("query")
    return task


def test_parse_typed_plan_and_code_block() -> None:
    plan = parse_task_plan(f"```json\n{json.dumps([_task('t1')])}\n```", 4)
    assert plan.tasks[0].type is TaskType.RAG


def test_parse_accepts_dependencies_and_legacy_refs() -> None:
    plan = parse_task_plan(json.dumps([_task("a"), _task("b", depends_on=["a"])]), 4)
    assert plan.tasks[1].depends_on == ("a",)
    assert plan.tasks[1].refs == ("a",)

    legacy_plan = parse_task_plan(json.dumps([_task("a"), {**_task("b"), "refs": ["a"]}]), 4)
    assert legacy_plan.tasks[1].depends_on == ("a",)


def test_parse_truncates_and_records_it() -> None:
    plan = parse_task_plan(json.dumps([_task(str(i)) for i in range(5)]), 2)
    assert len(plan.tasks) == 2
    assert plan.truncated is True


def test_parse_rejects_invalid_json_and_disallowed_type() -> None:
    with pytest.raises(ValueError):
        parse_task_plan("not json", 4)
    with pytest.raises(ValueError):
        parse_task_plan(json.dumps([_task("mcp", "MCP")]), 4, {TaskType.RAG})


def test_parse_validates_mcp_shape() -> None:
    with pytest.raises(ValueError):
        parse_task_plan(json.dumps([{**_task("mcp", "MCP"), "tool_ref": ""}]), 4)


def test_parse_rejects_invalid_dependency_graphs() -> None:
    with pytest.raises(ValueError, match="unknown dependency"):
        parse_task_plan(json.dumps([_task("b", depends_on=["missing"])]), 4)
    with pytest.raises(ValueError, match="acyclic"):
        parse_task_plan(json.dumps([_task("a", depends_on=["b"]), _task("b", depends_on=["a"])]), 4)
    with pytest.raises(ValueError, match="depth"):
        parse_task_plan(json.dumps([_task("a"), _task("b", depends_on=["a"]), _task("c", depends_on=["b"])]), 4)
    with pytest.raises(ValueError, match="MCP"):
        parse_task_plan(json.dumps([_task("a"), _task("mcp", "MCP", depends_on=["a"])]), 4)


def test_parse_validates_dependencies_after_truncation() -> None:
    with pytest.raises(ValueError, match="unknown dependency"):
        parse_task_plan(json.dumps([_task("b", depends_on=["a"]), _task("a")]), 1)


def test_fallback_plan_is_single_original_query_rag_task() -> None:
    plan = fallback_task_plan("original question", "invalid_json")
    assert plan.fallback is True
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type is TaskType.RAG
    assert plan.tasks[0].query == "original question"
