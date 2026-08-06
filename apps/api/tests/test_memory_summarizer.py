"""Unit tests for memory summarizer helpers and orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.memory_summarizer import MemorySummarizer, render_system_prompt, validate_jinja2_template


# --- render_system_prompt ---

def test_render_system_prompt_substitutes_variables() -> None:
    template = "SUMMARY OF {{ knowledge_base_name }} convo:\n{{ conversation_messages }}"
    result = render_system_prompt(
        template,
        conversation_messages="user: hello\nassistant: hi",
        knowledge_base_name="test-kb",
        turn_count=2,
    )
    assert "test-kb" in result
    assert "user: hello" in result


def test_render_system_prompt_includes_turn_count() -> None:
    template = "Turns: {{ turn_count }}"
    result = render_system_prompt(template, conversation_messages="", knowledge_base_name="kb", turn_count=5)
    assert "Turns: 5" in result


# --- validate_jinja2_template ---

def test_validate_jinja2_template_valid() -> None:
    assert validate_jinja2_template("Hello {{ name }}") is True


def test_validate_jinja2_template_invalid() -> None:
    assert validate_jinja2_template("{% invalid %}") is False


# --- MemorySummarizer orchestration ---

def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.qdrant_url = "http://qdrant:6333"
    settings.qdrant_api_key = None
    settings.ollama_base_url = "http://localhost:11434"
    return settings


def _make_config(enabled: bool = True, min_turns: int = 2) -> MagicMock:
    config = MagicMock()
    config.enabled = enabled
    config.min_turns_to_summarize = min_turns
    config.summarization_model_profile_id = "gen-1"
    config.embedding_profile_id = "emb-1"
    config.retention_days = 90
    config.system_prompt = "Summarize: {{ conversation_messages }}"
    return config


@pytest.mark.asyncio
async def test_summarize_returns_false_when_memory_disabled() -> None:
    settings = _make_settings()
    summarizer = MemorySummarizer(settings)
    session = MagicMock()

    chunk_repo = AsyncMock()
    chunk_repo.is_conversation_summarized.return_value = False

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_repo_cls, \
         patch("app.infrastructure.rag_conversations.SqlAlchemyConversationHistoryRepository") as conv_repo_cls:
        cfg_repo_cls.return_value.find_by_knowledge_base = AsyncMock(return_value=_make_config(enabled=False))
        chunk_repo_cls.return_value = chunk_repo
        conv_repo_cls.return_value = MagicMock()
        result = await summarizer.summarize(
            conversation_id="conv-1",
            tenant_id="tenant-1",
            knowledge_base_id="kb-1",
            user_id="user-1",
            session=session,
        )
    assert result is False


@pytest.mark.asyncio
async def test_summarize_returns_false_when_already_summarized() -> None:
    summarizer = MemorySummarizer(_make_settings())
    session = MagicMock()
    chunk_repo = AsyncMock()
    chunk_repo.is_conversation_summarized.return_value = True

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_repo_cls:
        cfg_repo_cls.return_value.find_by_knowledge_base = AsyncMock(return_value=_make_config(enabled=True))
        chunk_repo_cls.return_value = chunk_repo
        result = await summarizer.summarize(
            conversation_id="conv-1", tenant_id="tenant-1",
            knowledge_base_id="kb-1", user_id="user-1", session=session,
        )
    assert result is False


@pytest.mark.asyncio
async def test_summarize_returns_false_when_too_few_turns() -> None:
    summarizer = MemorySummarizer(_make_settings())
    session = MagicMock()
    chunk_repo = AsyncMock()
    chunk_repo.is_conversation_summarized.return_value = False
    conv_repo = MagicMock()
    conv_repo.recent_messages = AsyncMock(return_value=[])  # 0 turns < min 2

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_repo_cls, \
         patch("app.infrastructure.rag_conversations.SqlAlchemyConversationHistoryRepository") as conv_repo_cls:
        cfg_repo_cls.return_value.find_by_knowledge_base = AsyncMock(return_value=_make_config(enabled=True, min_turns=2))
        chunk_repo_cls.return_value = chunk_repo
        conv_repo_cls.return_value = conv_repo
        result = await summarizer.summarize(
            conversation_id="conv-1", tenant_id="tenant-1",
            knowledge_base_id="kb-1", user_id="user-1", session=session,
        )
    assert result is False


@pytest.mark.asyncio
async def test_summarize_full_flow_creates_chunk() -> None:
    summarizer = MemorySummarizer(_make_settings())
    session = AsyncMock()
    points = [
        MagicMock(speaker=MagicMock(value="USER"), content="hello"),
        MagicMock(speaker=MagicMock(value="ASSISTANT"), content="hi there"),
    ]
    conv_repo = MagicMock()
    conv_repo.recent_messages = AsyncMock(return_value=points)
    kb_repo = MagicMock()
    kb_repo.find_by_id = AsyncMock(return_value=MagicMock(name="test-kb"))

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_repo_cls, \
         patch("app.infrastructure.rag_conversations.SqlAlchemyConversationHistoryRepository") as conv_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyKnowledgeBaseRepository") as kb_repo_cls:
        cfg_repo_cls.return_value.find_by_knowledge_base = AsyncMock(return_value=_make_config(enabled=True, min_turns=1))
        chunk_repo = AsyncMock()
        chunk_repo.is_conversation_summarized.return_value = False
        chunk_repo_cls.return_value = chunk_repo
        conv_repo_cls.return_value = conv_repo
        kb_repo_cls.return_value = kb_repo
        summarizer._call_llm = AsyncMock(return_value="test summary")
        summarizer._embed = AsyncMock(return_value=[0.1, 0.2])
        summarizer._upsert_qdrant = AsyncMock()
        result = await summarizer.summarize(
            conversation_id="conv-1", tenant_id="tenant-1",
            knowledge_base_id="kb-1", user_id="user-1", session=session,
        )

    assert result is True
    chunk_repo.create.assert_awaited_once()