"""Unit tests for conversation history injection into generation.

Covers:
- GenerationAdapter protocol compliance (prompt-only and messages styles)
- LLMGenerationAdapter message formatting for OpenAI and Ollama
- RagQueryService._recent_messages() role mapping
- No conversation ID → empty messages
- Memory chunks and conversation history coexist
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.application.rag_generation import RagGenerationService
from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.rag.conversation import ConversationMessage, ConversationSpeaker
from app.domain.rag.evidence import Citation, EvidenceContext
from app.domain.tenant_context import TenantContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tenant() -> TenantContext:
    return TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)


def _evidence() -> EvidenceContext:
    return EvidenceContext(
        prompt_data="[SOURCE S1 | untrusted source data]\nsource text\n[END SOURCE S1]",
        citations=(Citation("S1", "chunk-1", "version-1", "Title", "page 1", "source text"),),
        token_count=5,
    )


def _message(speaker: ConversationSpeaker, content: str) -> ConversationMessage:
    from datetime import datetime

    return ConversationMessage(
        id=str(uuid4()),
        tenant_id="t1",
        conversation_id="c1",
        speaker=speaker,
        content=content,
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# 4.1 — GenerationAdapter protocol compliance
# ---------------------------------------------------------------------------


class GenerationStubWithMessages:
    """Stub that captures both prompt and messages kwargs."""

    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.prompt: str = ""
        self.messages: list[dict[str, str]] = []

    async def generate(
        self,
        *,
        tenant: TenantContext,
        prompt: str,
        model_profile_id: str,
        max_tokens: int | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        del tenant, model_profile_id, max_tokens
        self.prompt = prompt
        self.messages = messages or []
        return {"answer": self.answer}


@pytest.mark.asyncio
async def test_generation_service_prompt_only_backward_compat() -> None:
    """Calling generate() without messages works exactly as before."""
    stub = GenerationStubWithMessages({"facts": [], "inferences": [], "conflicts": [], "limitations": []})
    await RagGenerationService(Settings(_env_file=None), stub).generate(
        tenant=_tenant(), question="q", evidence=_evidence(), profile_id="p"
    )
    assert stub.messages == []
    assert stub.prompt != ""


@pytest.mark.asyncio
async def test_generation_service_forwards_messages_to_adapter() -> None:
    """RagGenerationService forwards messages array to the adapter."""
    stub = GenerationStubWithMessages({"facts": [], "inferences": [], "conflicts": [], "limitations": []})
    history = [{"role": "user", "content": "previous question"}, {"role": "assistant", "content": "previous answer"}]
    await RagGenerationService(Settings(_env_file=None), stub).generate(
        tenant=_tenant(), question="follow-up", evidence=_evidence(), profile_id="p", messages=history
    )
    assert stub.messages == history


# ---------------------------------------------------------------------------
# 4.2 — OpenAI message formatting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_openai_injects_history_between_system_and_user() -> None:
    """_call_openai inserts history messages after system and before final user."""
    from app.infrastructure.generation_adapter import _call_openai

    captured: list[dict[str, str]] = []

    async def fake_create(**kwargs: object) -> object:
        captured.extend(kwargs["messages"])  # type: ignore[arg-type]
        result = MagicMock()
        result.choices = [MagicMock()]
        result.choices[0].message.content = '{"facts":[],"inferences":[],"conflicts":[],"limitations":[]}'
        return result

    history = [{"role": "user", "content": "prior q"}, {"role": "assistant", "content": "prior a"}]

    with patch("openai.AsyncOpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)

        await _call_openai(
            model="gpt-4o",
            api_key="sk-test",
            system_prompt="system",
            user_prompt="user prompt",
            max_tokens=512,
            history=history,
        )

    roles = [m["role"] for m in captured]
    assert roles == ["system", "user", "assistant", "user"]
    assert captured[0]["content"] == "system"
    assert captured[1]["content"] == "prior q"
    assert captured[2]["content"] == "prior a"
    assert captured[3]["content"] == "user prompt"


@pytest.mark.asyncio
async def test_call_openai_no_history_sends_system_and_user_only() -> None:
    """_call_openai with empty history sends only system + user (backward compat)."""
    from app.infrastructure.generation_adapter import _call_openai

    captured: list[dict[str, str]] = []

    async def fake_create(**kwargs: object) -> object:
        captured.extend(kwargs["messages"])  # type: ignore[arg-type]
        result = MagicMock()
        result.choices = [MagicMock()]
        result.choices[0].message.content = '{"facts":[],"inferences":[],"conflicts":[],"limitations":[]}'
        return result

    with patch("openai.AsyncOpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)

        await _call_openai(
            model="gpt-4o",
            api_key="sk-test",
            system_prompt="system",
            user_prompt="user prompt",
            max_tokens=512,
            history=[],
        )

    roles = [m["role"] for m in captured]
    assert roles == ["system", "user"]


# ---------------------------------------------------------------------------
# 4.3 — Ollama message formatting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_ollama_injects_history_between_system_and_user() -> None:
    """_call_ollama inserts history messages after system and before final user."""
    import httpx

    from app.infrastructure.generation_adapter import _call_ollama

    history = [{"role": "user", "content": "prior q"}, {"role": "assistant", "content": "prior a"}]
    captured_messages: list[dict[str, str]] = []

    async def fake_post(url: str, **kwargs: object) -> object:
        json_body = kwargs.get("json", {})
        captured_messages.extend(json_body.get("messages", []))  # type: ignore[union-attr]
        response = MagicMock(spec=httpx.Response)
        response.raise_for_status = MagicMock()
        response.json.return_value = {"message": {"content": '{"facts":[],"inferences":[],"conflicts":[],"limitations":[]}'}}
        return response

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=fake_post)

        await _call_ollama(
            model="llama3",
            base_url="http://localhost:11434",
            system_prompt="system",
            user_prompt="user prompt",
            history=history,
        )

    roles = [m["role"] for m in captured_messages]
    assert roles == ["system", "user", "assistant", "user"]


# ---------------------------------------------------------------------------
# 4.4 — RagQueryService._recent_messages() role mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_messages_maps_speaker_to_role() -> None:
    """_recent_messages maps USER → 'user' and ASSISTANT → 'assistant'."""
    from app.application.rag_query_service import RagQueryService

    tenant = _tenant()
    msgs = [
        _message(ConversationSpeaker.USER, "hello"),
        _message(ConversationSpeaker.ASSISTANT, "hi there"),
        _message(ConversationSpeaker.USER, "follow-up"),
    ]

    mock_repo = AsyncMock()
    mock_repo.recent_messages = AsyncMock(return_value=msgs)

    service = RagQueryService.__new__(RagQueryService)
    service._conversations = mock_repo
    service._settings = Settings(_env_file=None)

    result = await service._recent_messages(tenant=tenant, conversation_id="conv-1")

    assert result == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "follow-up"},
    ]


# ---------------------------------------------------------------------------
# 4.5 — No conversation ID → empty messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_messages_returns_empty_when_no_conversation_id() -> None:
    """_recent_messages returns [] without calling the repo when conversation_id is None."""
    from app.application.rag_query_service import RagQueryService

    tenant = _tenant()
    mock_repo = AsyncMock()

    service = RagQueryService.__new__(RagQueryService)
    service._conversations = mock_repo
    service._settings = Settings(_env_file=None)

    result = await service._recent_messages(tenant=tenant, conversation_id=None)

    assert result == []
    mock_repo.recent_messages.assert_not_called()


# ---------------------------------------------------------------------------
# 4.6 — Memory chunks and conversation history coexist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generation_receives_both_history_and_supplementary() -> None:
    """When both messages and supplementary are provided, adapter receives both."""
    stub = GenerationStubWithMessages({"facts": [], "inferences": [], "conflicts": [], "limitations": []})
    history = [{"role": "user", "content": "prior q"}]
    supplementary = "Long-term memory context block"

    await RagGenerationService(Settings(_env_file=None), stub).generate(
        tenant=_tenant(),
        question="new question",
        evidence=_evidence(),
        profile_id="p",
        supplementary=supplementary,
        messages=history,
    )

    assert stub.messages == history
    assert supplementary in stub.prompt


@pytest.mark.asyncio
async def test_generation_works_with_only_supplementary_no_history() -> None:
    """Existing memory-only path still works when no conversation history is present."""
    stub = GenerationStubWithMessages({"facts": [], "inferences": [], "conflicts": [], "limitations": []})
    supplementary = "Long-term memory context block"

    await RagGenerationService(Settings(_env_file=None), stub).generate(
        tenant=_tenant(),
        question="q",
        evidence=_evidence(),
        profile_id="p",
        supplementary=supplementary,
    )

    assert stub.messages == []
    assert supplementary in stub.prompt
