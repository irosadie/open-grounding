import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.application.task_executor import TaskExecutor
from app.core.llm_rollout_trace import rollout_context
from app.core.settings import Settings
from app.domain.rag.task_plan import TaskSpec, TaskType


def test_rollout_trace_settings_are_disabled_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.rag_llm_trace_enabled is False
    assert settings.rag_llm_trace_dir == ".runtime/llm-traces"


def test_rollout_trace_settings_accept_boolean_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_LLM_TRACE_ENABLED", "true")
    assert Settings(_env_file=None).rag_llm_trace_enabled is True

    monkeypatch.setenv("RAG_LLM_TRACE_ENABLED", "false")
    assert Settings(_env_file=None).rag_llm_trace_enabled is False


@pytest.mark.asyncio
async def test_disabled_rollout_trace_does_not_create_files(tmp_path: Path) -> None:
    async with rollout_context(trace_id="disabled", source="test", trace_dir=tmp_path, enabled=False) as trace:
        trace.record("user_message", {"content": "hello"})

    assert list(tmp_path.rglob("*")) == []


@pytest.mark.asyncio
async def test_enabled_rollout_trace_writes_ordered_jsonl_and_redacts_secrets(tmp_path: Path) -> None:
    async with rollout_context(trace_id="trace-1", source="test", trace_dir=tmp_path, enabled=True) as trace:
        trace.record(
            "llm_request",
            {
                "headers": {"Authorization": "Bearer secret-token"},
                "messages": [{"role": "user", "content": "keep this prompt"}],
                "url": "https://provider.test/chat?api_key=secret-key&mode=debug",
            },
        )
        trace.record("tool_result", {"result": "keep this tool output"})

    files = list(tmp_path.rglob("rollout-trace-1.jsonl"))
    assert len(files) == 1
    events = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert [event["seq"] for event in events] == [1, 2, 3, 4]
    assert all({"schema_version", "seq", "ts", "trace_id", "event", "payload"} <= set(event) for event in events)
    assert events[1]["event"] == "llm_request"
    assert events[1]["payload"]["headers"]["Authorization"] == "[REDACTED]"
    assert events[1]["payload"]["messages"][0]["content"] == "keep this prompt"
    assert "secret-key" not in events[1]["payload"]["url"]
    assert events[2]["payload"]["result"] == "keep this tool output"


@pytest.mark.asyncio
async def test_generation_provider_records_exact_request_and_response(tmp_path: Path) -> None:
    from app.infrastructure.generation_adapter import _call_openai

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"facts":[]}'))],
        id="response-1",
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=response)),
        ),
    )

    with patch("openai.AsyncOpenAI", return_value=client):
        async with rollout_context(trace_id="provider-trace", source="test", trace_dir=tmp_path, enabled=True):
            content = await _call_openai(
                model="test-model",
                api_key="secret-api-key",
                system_prompt="system instructions",
                user_prompt="user question",
                max_tokens=128,
                history=[{"role": "user", "content": "previous turn"}],
            )

    assert content == '{"facts":[]}'
    path = next(tmp_path.rglob("rollout-provider-trace.jsonl"))
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    request = next(event for event in events if event["event"] == "llm_request")
    result = next(event for event in events if event["event"] == "llm_response")
    assert request["payload"]["request"]["messages"][-1] == {"role": "user", "content": "user question"}
    assert request["payload"]["request"]["max_completion_tokens"] == 128
    assert result["payload"]["content"] == '{"facts":[]}'


@pytest.mark.asyncio
async def test_generation_provider_error_is_recorded_without_hiding_the_error(tmp_path: Path) -> None:
    from app.infrastructure.generation_adapter import _call_openai

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("provider down"))),
        ),
    )

    with patch("openai.AsyncOpenAI", return_value=client):
        with pytest.raises(RuntimeError, match="provider down"):
            async with rollout_context(trace_id="provider-error", source="test", trace_dir=tmp_path, enabled=True):
                await _call_openai(
                    model="test-model",
                    api_key="secret-api-key",
                    system_prompt="system instructions",
                    user_prompt="user question",
                    max_tokens=128,
                    history=[],
                )

    path = next(tmp_path.rglob("rollout-provider-error.jsonl"))
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    error = next(event for event in events if event["event"] == "llm_error")
    assert error["parent_seq"] == 2
    assert error["payload"]["error"] == "provider down"


@pytest.mark.asyncio
async def test_task_executor_records_agent_task_lifecycle(tmp_path: Path) -> None:
    async def rag(_: TaskSpec) -> list[dict[str, object]]:
        return [{"id": "chunk-1"}]

    async def general(_: TaskSpec) -> str:
        return "answer"

    async with rollout_context(trace_id="task-trace", source="test", trace_dir=tmp_path, enabled=True):
        results = await TaskExecutor(rag_handler=rag, general_handler=general).execute(
            [TaskSpec("rag", TaskType.RAG, "retrieve", query="question")]
        )

    assert results[0].status == "success"
    path = next(tmp_path.rglob("rollout-task-trace.jsonl"))
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    names = [event["event"] for event in events]
    assert "agent_task_started" in names
    assert "agent_task_completed" in names
    completed = next(event for event in events if event["event"] == "agent_task_completed")
    assert completed["payload"]["status"] == "success"


@pytest.mark.asyncio
async def test_concurrent_rollouts_are_isolated(tmp_path: Path) -> None:
    async def write_trace(trace_id: str) -> None:
        async with rollout_context(trace_id=trace_id, source="test", trace_dir=tmp_path, enabled=True) as trace:
            await asyncio.sleep(0)
            trace.record("user_message", {"trace_id": trace_id})

    await asyncio.gather(write_trace("trace-a"), write_trace("trace-b"))

    files = sorted(tmp_path.rglob("rollout-*.jsonl"))
    assert [path.name for path in files] == ["rollout-trace-a.jsonl", "rollout-trace-b.jsonl"]
    for path in files:
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert {event["trace_id"] for event in events} == {path.stem.removeprefix("rollout-")}
