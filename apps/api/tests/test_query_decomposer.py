"""Unit tests for QueryDecomposer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.query_decomposer import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
    DecompositionResult,
    QueryDecomposer,
    _parse_sub_queries,
    _render,
    validate_template,
)


# --- validate_template ---

def test_validate_template_valid() -> None:
    validate_template("Hello {{ name }}")


def test_validate_template_invalid() -> None:
    from jinja2 import TemplateSyntaxError
    with pytest.raises(TemplateSyntaxError):
        validate_template("{% invalid %}")


# --- _render ---

def test_render_substitutes_variables() -> None:
    result = _render("Query: {{ query }}", {"query": "test query"})
    assert result == "Query: test query"


def test_render_with_max_sub_queries() -> None:
    result = _render("Max: {{ max_sub_queries }}", {"max_sub_queries": 3})
    assert result == "Max: 3"


# --- _parse_sub_queries ---

def test_parse_valid_json_array() -> None:
    raw = json.dumps(["query 1", "query 2", "query 3"])
    result = _parse_sub_queries(raw, max_sub_queries=5)
    assert result == ["query 1", "query 2", "query 3"]


def test_parse_truncates_to_max() -> None:
    raw = json.dumps(["q1", "q2", "q3", "q4", "q5"])
    result = _parse_sub_queries(raw, max_sub_queries=3)
    assert len(result) == 3


def test_parse_strips_empty_strings() -> None:
    raw = json.dumps(["q1", "", "  ", "q2"])
    result = _parse_sub_queries(raw, max_sub_queries=5)
    assert result == ["q1", "q2"]


def test_parse_strips_markdown_code_block() -> None:
    raw = "```json\n[\"q1\", \"q2\"]\n```"
    result = _parse_sub_queries(raw, max_sub_queries=5)
    assert result == ["q1", "q2"]


def test_parse_raises_on_invalid_json() -> None:
    with pytest.raises(Exception):
        _parse_sub_queries("not json", max_sub_queries=5)


def test_parse_raises_on_non_array() -> None:
    with pytest.raises(ValueError):
        _parse_sub_queries('{"key": "value"}', max_sub_queries=5)


# --- QueryDecomposer ---

def _make_config(
    max_sub_queries: int = 3,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    user_prompt_template: str = DEFAULT_USER_PROMPT_TEMPLATE,
) -> MagicMock:
    config = MagicMock()
    config.tenant_id = "tenant-1"
    config.max_sub_queries = max_sub_queries
    config.system_prompt = system_prompt
    config.user_prompt_template = user_prompt_template
    return config


def _make_model_profile(provider: str = "openai", model: str = "gpt-4o-mini") -> MagicMock:
    profile = MagicMock()
    profile.provider = provider
    profile.model = model
    return profile


@pytest.mark.asyncio
async def test_decompose_returns_sub_queries_on_success() -> None:
    settings = MagicMock()
    decomposer = QueryDecomposer(settings)

    sub_queries = ["query about A", "query about B"]
    with patch.object(decomposer, "_call_llm", new=AsyncMock(return_value=json.dumps(sub_queries))):
        result = await decomposer.decompose(
            query="Complex query about A and B",
            config=_make_config(),
            knowledge_base_name="test-kb",
            model_profile=_make_model_profile(),
        )

    assert result.fallback is False
    assert result.sub_queries == sub_queries


@pytest.mark.asyncio
async def test_decompose_fallback_on_timeout() -> None:
    import asyncio
    settings = MagicMock()
    decomposer = QueryDecomposer(settings)

    with patch.object(decomposer, "_call_llm", new=AsyncMock(side_effect=asyncio.TimeoutError)):
        result = await decomposer.decompose(
            query="test query",
            config=_make_config(),
            knowledge_base_name="test-kb",
            model_profile=_make_model_profile(),
        )

    assert result.fallback is True
    assert result.fallback_reason == "timeout"
    assert result.sub_queries == ["test query"]


@pytest.mark.asyncio
async def test_decompose_fallback_on_llm_error() -> None:
    settings = MagicMock()
    decomposer = QueryDecomposer(settings)

    with patch.object(decomposer, "_call_llm", new=AsyncMock(side_effect=ValueError("API error"))):
        result = await decomposer.decompose(
            query="test query",
            config=_make_config(),
            knowledge_base_name="test-kb",
            model_profile=_make_model_profile(),
        )

    assert result.fallback is True
    assert "llm_error" in (result.fallback_reason or "")


@pytest.mark.asyncio
async def test_decompose_fallback_on_invalid_json() -> None:
    settings = MagicMock()
    decomposer = QueryDecomposer(settings)

    with patch.object(decomposer, "_call_llm", new=AsyncMock(return_value="not valid json")):
        result = await decomposer.decompose(
            query="test query",
            config=_make_config(),
            knowledge_base_name="test-kb",
            model_profile=_make_model_profile(),
        )

    assert result.fallback is True


@pytest.mark.asyncio
async def test_decompose_fallback_on_empty_sub_queries() -> None:
    settings = MagicMock()
    decomposer = QueryDecomposer(settings)

    with patch.object(decomposer, "_call_llm", new=AsyncMock(return_value="[]")):
        result = await decomposer.decompose(
            query="test query",
            config=_make_config(),
            knowledge_base_name="test-kb",
            model_profile=_make_model_profile(),
        )

    assert result.fallback is True
    assert result.fallback_reason == "empty_sub_queries"


@pytest.mark.asyncio
async def test_decompose_fallback_on_template_error() -> None:
    settings = MagicMock()
    decomposer = QueryDecomposer(settings)
    config = _make_config(system_prompt="{% invalid %}")

    result = await decomposer.decompose(
        query="test query",
        config=config,
        knowledge_base_name="test-kb",
        model_profile=_make_model_profile(),
    )

    assert result.fallback is True
    assert "template_render_error" in (result.fallback_reason or "")
