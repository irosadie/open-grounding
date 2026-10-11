"""Unit tests for memory summarizer helpers and orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.memory_summarizer import (
    MAX_MEMORY_SUMMARY_CHARS,
    MemoryDecision,
    MemorySummarizer,
    _call_openai_llm,
    _ensure_memory_collection,
    extract_explicit_memory_summary,
    has_explicit_memory_request,
    parse_memory_decision,
    render_system_prompt,
    validate_jinja2_template,
)

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
    assert '"should_store": true|false' in result
    assert "USER messages as the authority" in result
    assert "source-only facts" in result


def test_render_system_prompt_includes_turn_count() -> None:
    template = "Turns: {{ turn_count }}"
    result = render_system_prompt(template, conversation_messages="", knowledge_base_name="kb", turn_count=5)
    assert "Turns: 5" in result


def test_render_system_prompt_prioritizes_explicit_memory_requests_without_bypassing_filters() -> None:
    result = render_system_prompt(
        "{{ conversation_messages }}",
        conversation_messages="USER: Please remember my name is Alya.",
        knowledge_base_name="kb",
        turn_count=2,
        explicit_memory_request=True,
    )

    assert "explicit USER request" in result
    assert "does not override the exclusions for secrets" in result
    assert "my name is Alya" in result
    assert "generic consent" in result
    assert "HARD RULE FOR THIS CONVERSATION" in result
    assert "ATURAN WAJIB UNTUK PERMINTAAN BAHASA INDONESIA" in result
    assert "simpan informasi nama saya" in result


@pytest.mark.parametrize(
    "content",
    [
        "saya mau kamu simpan informasi nama saya, saya adalah Alya",
        "Tolong ingat bahwa saya suka jawaban ringkas",
        "Please remember that my name is Alya",
        "Save this preference for future sessions",
    ],
)
def test_has_explicit_memory_request_accepts_supported_wording(content: str) -> None:
    assert has_explicit_memory_request([MagicMock(speaker=MagicMock(value="USER"), content=content)]) is True


def test_has_explicit_memory_request_ignores_assistant_messages() -> None:
    messages = [
        MagicMock(speaker=MagicMock(value="ASSISTANT"), content="Please remember my name."),
        MagicMock(speaker=MagicMock(value="USER"), content="What is the weather?"),
    ]

    assert has_explicit_memory_request(messages) is False


def test_extract_explicit_memory_summary_prefers_concrete_name_over_consent() -> None:
    messages = [
        MagicMock(
            speaker=MagicMock(value="USER"),
            content="saya mau kamu simpan informasi nama saya, saya adalah Alya",
        )
    ]

    assert extract_explicit_memory_summary(messages) == "Pengguna menyatakan bahwa namanya adalah Alya."


def test_extract_explicit_memory_summary_rejects_secret_content() -> None:
    messages = [
        MagicMock(speaker=MagicMock(value="USER"), content="simpan password saya: rahasia123"),
    ]

    assert extract_explicit_memory_summary(messages) is None


# --- parse_memory_decision ---

def test_parse_memory_decision_accepts_durable_summary() -> None:
    result = parse_memory_decision(
        '{"should_store": true, "summary": "The user prefers concise answers.", "reason": "preference"}'
    )

    assert result == MemoryDecision(True, "The user prefers concise answers.", "preference")


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("not json", "invalid_json"),
        ('{"should_store": "yes", "summary": "fact"}', "invalid_should_store"),
        ('{"should_store": true}', "missing_summary"),
        ('{"should_store": true, "summary": "x"}', "accepted"),
    ],
)
def test_parse_memory_decision_fails_closed(raw: str, reason: str) -> None:
    result = parse_memory_decision(raw, max_summary_chars=1)

    if reason == "accepted":
        assert result.should_store is True
    else:
        assert result.should_store is False
        assert result.reason == reason


def test_parse_memory_decision_rejects_oversized_summary() -> None:
    result = parse_memory_decision(
        '{"should_store": true, "summary": "' + ("x" * (MAX_MEMORY_SUMMARY_CHARS + 1)) + '"}'
    )

    assert result == MemoryDecision(False, None, "summary_too_long")


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
async def test_summarize_evaluates_explicit_save_request_below_threshold() -> None:
    summarizer = MemorySummarizer(_make_settings())
    session = AsyncMock()
    conv_repo = MagicMock()
    conv_repo.recent_messages = AsyncMock(
        return_value=[
            MagicMock(
                speaker=MagicMock(value="USER"),
                content="saya mau kamu simpan informasi nama saya, saya adalah Alya",
            ),
            MagicMock(speaker=MagicMock(value="ASSISTANT"), content="Baik, saya mengerti."),
        ]
    )
    kb_repo = MagicMock()
    kb_repo.find_by_id = AsyncMock(return_value=MagicMock(name="test-kb"))

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_repo_cls, \
         patch("app.infrastructure.rag_conversations.SqlAlchemyConversationHistoryRepository") as conv_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyKnowledgeBaseRepository") as kb_repo_cls:
        cfg_repo_cls.return_value.find_by_knowledge_base = AsyncMock(return_value=_make_config(enabled=True, min_turns=3))
        chunk_repo = AsyncMock()
        chunk_repo.is_conversation_summarized.return_value = False
        chunk_repo_cls.return_value = chunk_repo
        conv_repo_cls.return_value = conv_repo
        kb_repo_cls.return_value = kb_repo
        summarizer._call_llm = AsyncMock(return_value=MemoryDecision(False, None, "izin umum, bukan fakta konkret"))
        summarizer._embed = AsyncMock(return_value=[0.1, 0.2])
        summarizer._upsert_qdrant = AsyncMock()

        result = await summarizer.summarize(
            conversation_id="conv-1", tenant_id="tenant-1",
            knowledge_base_id="kb-1", user_id="user-1", session=session,
        )

    assert result is True
    summarizer._call_llm.assert_awaited_once()
    assert "HARD RULE FOR THIS CONVERSATION" in summarizer._call_llm.await_args.kwargs["prompt"]
    chunk_repo.create.assert_awaited_once()
    assert chunk_repo.create.await_args.kwargs["summary"] == "Pengguna menyatakan bahwa namanya adalah Alya."


@pytest.mark.asyncio
async def test_summarize_keeps_threshold_for_ordinary_short_conversation() -> None:
    summarizer = MemorySummarizer(_make_settings())
    session = MagicMock()
    conv_repo = MagicMock()
    conv_repo.recent_messages = AsyncMock(
        return_value=[
            MagicMock(speaker=MagicMock(value="USER"), content="Apa kabar?"),
            MagicMock(speaker=MagicMock(value="ASSISTANT"), content="Baik."),
        ]
    )

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_repo_cls, \
         patch("app.infrastructure.rag_conversations.SqlAlchemyConversationHistoryRepository") as conv_repo_cls:
        cfg_repo_cls.return_value.find_by_knowledge_base = AsyncMock(return_value=_make_config(enabled=True, min_turns=3))
        chunk_repo = AsyncMock()
        chunk_repo.is_conversation_summarized.return_value = False
        chunk_repo_cls.return_value = chunk_repo
        conv_repo_cls.return_value = conv_repo
        summarizer._call_llm = AsyncMock()

        result = await summarizer.summarize(
            conversation_id="conv-1", tenant_id="tenant-1",
            knowledge_base_id="kb-1", user_id="user-1", session=session,
        )

    assert result is False
    summarizer._call_llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_summarize_full_flow_creates_chunk() -> None:
    summarizer = MemorySummarizer(_make_settings())
    session = AsyncMock()
    points = [
        MagicMock(speaker=MagicMock(value="USER"), content="I live in Bandung."),
        MagicMock(speaker=MagicMock(value="ASSISTANT"), content="The retrieved document says Pekanbaru."),
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
        summarizer._call_llm = AsyncMock(
            return_value=MemoryDecision(
                True,
                "The user says they live in Bandung.",
                "durable user-stated fact",
            )
        )
        summarizer._embed = AsyncMock(return_value=[0.1, 0.2])
        summarizer._upsert_qdrant = AsyncMock()
        result = await summarizer.summarize(
            conversation_id="conv-1", tenant_id="tenant-1",
            knowledge_base_id="kb-1", user_id="user-1", session=session,
        )

    assert result is True
    chunk_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_summarize_does_not_persist_when_memory_llm_rejects() -> None:
    summarizer = MemorySummarizer(_make_settings())
    session = AsyncMock()
    conv_repo = MagicMock()
    conv_repo.recent_messages = AsyncMock(
        return_value=[
            MagicMock(speaker=MagicMock(value="USER"), content="What is my address?"),
            MagicMock(speaker=MagicMock(value="ASSISTANT"), content="The document says Pekanbaru."),
        ]
    )

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_repo_cls, \
         patch("app.infrastructure.rag_conversations.SqlAlchemyConversationHistoryRepository") as conv_repo_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyKnowledgeBaseRepository") as kb_repo_cls:
        cfg_repo_cls.return_value.find_by_knowledge_base = AsyncMock(return_value=_make_config(enabled=True, min_turns=1))
        chunk_repo = AsyncMock()
        chunk_repo.is_conversation_summarized.return_value = False
        chunk_repo_cls.return_value = chunk_repo
        conv_repo_cls.return_value = conv_repo
        kb_repo_cls.return_value.find_by_id = AsyncMock(return_value=MagicMock(name="test-kb"))
        summarizer._call_llm = AsyncMock(
            return_value=MemoryDecision(False, None, "source_only")
        )
        summarizer._embed = AsyncMock()
        summarizer._upsert_qdrant = AsyncMock()

        result = await summarizer.summarize(
            conversation_id="conv-1", tenant_id="tenant-1",
            knowledge_base_id="kb-1", user_id="user-1", session=session,
        )

    assert result is False
    chunk_repo.create.assert_not_awaited()
    summarizer._embed.assert_not_awaited()
    summarizer._upsert_qdrant.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_llm_parses_provider_decision_envelope() -> None:
    summarizer = MemorySummarizer(_make_settings())
    profile = SimpleNamespace(provider="openai", model="gpt-5-mini")
    raw = '{"should_store": true, "summary": "The user prefers concise answers."}'

    with patch("app.infrastructure.rag_catalog.SqlAlchemyModelProfileRepository") as profile_repo_cls, \
         patch("app.application.memory_summarizer._get_api_key", new_callable=AsyncMock, return_value="api-key"), \
         patch("app.application.memory_summarizer._call_openai_llm", new_callable=AsyncMock, return_value=raw):
        profile_repo_cls.return_value.find_by_id = AsyncMock(return_value=profile)
        result = await summarizer._call_llm(
            tenant_id="tenant-1",
            model_profile_id="gen-1",
            prompt="memory prompt",
            session=AsyncMock(),
        )

    assert result == MemoryDecision(True, "The user prefers concise answers.", "accepted")


@pytest.mark.asyncio
async def test_openai_summarizer_uses_provider_default_temperature() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="test summary"))]
    )
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    with patch("openai.AsyncOpenAI", return_value=client):
        result = await _call_openai_llm("gpt-5-mini", "Summarize this", "api-key")

    assert result == "test summary"
    request = client.chat.completions.create.call_args.kwargs
    assert "temperature" not in request


@pytest.mark.asyncio
async def test_ensure_memory_collection_creates_missing_collection() -> None:
    client = MagicMock()
    missing = MagicMock(status_code=404)
    created = MagicMock(status_code=200)
    client.get = AsyncMock(return_value=missing)
    client.put = AsyncMock(return_value=created)

    await _ensure_memory_collection(
        client=client,
        base_url="http://qdrant:6333",
        headers={"api-key": "test-key"},
        vector_size=384,
    )

    client.get.assert_awaited_once_with(
        "http://qdrant:6333/collections/memory",
        headers={"api-key": "test-key"},
    )
    client.put.assert_awaited_once_with(
        "http://qdrant:6333/collections/memory",
        headers={"api-key": "test-key"},
        json={"vectors": {"size": 384, "distance": "Cosine"}},
    )
