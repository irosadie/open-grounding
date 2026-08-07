import json

import pytest

from app.domain.rag.task_plan import TaskType, parse_task_plan
from app.domain.rag.task_plan import fallback_task_plan


def _task(task_id: str, task_type: str = "RAG") -> dict[str, object]:
    return {"id": task_id, "type": task_type, "intent": "answer", "query": "test"}


def test_parse_typed_plan_and_code_block() -> None:
    plan = parse_task_plan(f"```json\n{json.dumps([_task('t1')])}\n```", 4)
    assert plan.tasks[0].type is TaskType.RAG


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
        parse_task_plan(json.dumps([_task("mcp", "MCP")]), 4)


def test_fallback_plan_is_single_original_query_rag_task() -> None:
    plan = fallback_task_plan("original question", "invalid_json")
    assert plan.fallback is True
    assert len(plan.tasks) == 1
    assert plan.tasks[0].type is TaskType.RAG
    assert plan.tasks[0].query == "original question"
