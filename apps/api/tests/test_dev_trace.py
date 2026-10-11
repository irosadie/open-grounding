import json
from types import SimpleNamespace

import pytest

from app.core.dev_trace import DevTracer, get_tracer, reset_tracer
from app.core.settings import Settings


@pytest.fixture(autouse=True)
def reset_dev_tracer() -> None:
    reset_tracer()
    yield
    reset_tracer()


def test_settings_default_and_valid_modes() -> None:
    assert Settings(_env_file=None).rag_dev_trace == "off"
    assert Settings(_env_file=None, rag_dev_trace="summary").rag_dev_trace == "summary"
    assert Settings(_env_file=None, rag_dev_trace="verbose").rag_dev_trace == "verbose"


def test_get_tracer_is_a_lazy_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.settings.get_settings",
        lambda: SimpleNamespace(rag_dev_trace="summary"),
    )

    first = get_tracer()
    second = get_tracer()

    assert first is second
    assert first.enabled is True
    assert first.mode == "summary"


@pytest.mark.asyncio
async def test_disabled_tracer_emits_no_output(capsys: pytest.CaptureFixture[str]) -> None:
    tracer = DevTracer("off")

    async with tracer.op("query.plan", route="GROUNDED"):
        pass
    tracer.emit("query.evidence", chunks=2)

    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_summary_trace_is_human_readable_and_times_work(capsys: pytest.CaptureFixture[str]) -> None:
    tracer = DevTracer("summary")

    async with tracer.op("query.plan", route="GROUNDED", types=["RAG", "MCP"]):
        pass

    line = capsys.readouterr().out.strip()
    assert line.startswith("[DEV] query.plan route=GROUNDED types=RAG,MCP ms=")


@pytest.mark.asyncio
async def test_verbose_trace_is_ndjson_and_redacts_full_prompt_values(capsys: pytest.CaptureFixture[str]) -> None:
    tracer = DevTracer("verbose")
    system_prompt = "s" * 400
    user_prompt = "u" * 400

    async with tracer.op(
        "query.llm_context",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        verbose_meta={"tasks": [{"type": "RAG"}], "token_estimate": 200},
    ):
        pass

    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "query.llm_context"
    assert event["system_tail"] == system_prompt[-300:]
    assert event["user_tail"] == user_prompt[-300:]
    assert "system_prompt" not in event
    assert "user_prompt" not in event
    assert event["tasks"] == [{"type": "RAG"}]
    assert event["token_estimate"] == 200
    assert isinstance(event["ms"], (int, float))


@pytest.mark.asyncio
async def test_trace_is_emitted_when_operation_fails_without_swallowing_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tracer = DevTracer("verbose")

    with pytest.raises(RuntimeError, match="provider down"):
        async with tracer.op("query.generation"):
            raise RuntimeError("provider down")

    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "query.generation"
    assert event["error_type"] == "RuntimeError"
