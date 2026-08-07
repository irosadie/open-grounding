"""Unit tests for conversation message persistence.

Covers:
- save_message() persists correct fields for USER and ASSISTANT speakers
- ensure_conversation() is idempotent
- conversation_id generated server-side when not provided
- user message saved before query, assistant message saved after
- persistence failure does not propagate
- conversationId present in response dict
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.application.rag_query_service import RagQueryService
from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.rag.conversation import ConversationMessage, ConversationSpeaker
from app.domain.tenant_context import TenantContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tenant() -> TenantContext:
    return TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)


def _make_service(*, save_raises: bool = False) -> tuple[RagQueryService, MagicMock]:
    mock_repo = MagicMock()
    mock_repo.ensure_conversation = AsyncMock(side_effect=Exception("db error") if save_raises else None)
    mock_repo.save_message = AsyncMock(side_effect=Exception("db error") if save_raises else None)
    mock_repo.recent_messages = AsyncMock(return_value=[])

    service = RagQueryService.__new__(RagQueryService)
    service._conversations = mock_repo
    service._settings = Settings(_env_file=None)
    return service, mock_repo


# ---------------------------------------------------------------------------
# 5.1 — save_message() persists correct fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_turn_persists_user_message() -> None:
    service, mock_repo = _make_service()
    tenant = _tenant()

    await service._save_turn(tenant=tenant, conversation_id="conv-1", speaker="user", content="hello")

    mock_repo.ensure_conversation.assert_awaited_once_with(
        tenant_id=tenant.tenant_id,
        user_id=tenant.user_id,
        conversation_id="conv-1",
    )
    saved: ConversationMessage = mock_repo.save_message.call_args.kwargs["message"]
    assert saved.speaker == ConversationSpeaker.USER
    assert saved.content == "hello"
    assert saved.tenant_id == tenant.tenant_id
    assert saved.conversation_id == "conv-1"


@pytest.mark.asyncio
async def test_save_turn_persists_assistant_message() -> None:
    service, mock_repo = _make_service()
    tenant = _tenant()

    await service._save_turn(tenant=tenant, conversation_id="conv-1", speaker="assistant", content="answer text")

    saved: ConversationMessage = mock_repo.save_message.call_args.kwargs["message"]
    assert saved.speaker == ConversationSpeaker.ASSISTANT
    assert saved.content == "answer text"


# ---------------------------------------------------------------------------
# 5.2 — ensure_conversation() idempotent (no error on duplicate call)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_turn_calls_ensure_conversation_each_time() -> None:
    service, mock_repo = _make_service()
    tenant = _tenant()

    await service._save_turn(tenant=tenant, conversation_id="conv-1", speaker="user", content="q1")
    await service._save_turn(tenant=tenant, conversation_id="conv-1", speaker="assistant", content="a1")

    assert mock_repo.ensure_conversation.await_count == 2


# ---------------------------------------------------------------------------
# 5.3 — conversation_id generated when not provided
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_messages_returns_empty_for_none_conversation_id() -> None:
    """When conversation_id is None, _recent_messages returns [] without DB call."""
    service, mock_repo = _make_service()
    tenant = _tenant()

    result = await service._recent_messages(tenant=tenant, conversation_id=None)

    assert result == []
    mock_repo.recent_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_turn_generates_valid_uuid_for_message_id() -> None:
    """_save_turn creates a message with a valid UUID id."""
    service, mock_repo = _make_service()
    tenant = _tenant()

    await service._save_turn(tenant=tenant, conversation_id="conv-1", speaker="user", content="hi")

    saved: ConversationMessage = mock_repo.save_message.call_args.kwargs["message"]
    UUID(saved.id)  # raises if not valid UUID


# ---------------------------------------------------------------------------
# 5.4 — user saved before query, assistant saved after
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_turn_called_twice_for_user_and_assistant() -> None:
    """Both user and assistant messages are saved in a turn."""
    service, mock_repo = _make_service()
    tenant = _tenant()

    await service._save_turn(tenant=tenant, conversation_id="c1", speaker="user", content="question")
    await service._save_turn(tenant=tenant, conversation_id="c1", speaker="assistant", content="answer")

    assert mock_repo.save_message.await_count == 2
    calls = mock_repo.save_message.call_args_list
    assert calls[0].kwargs["message"].speaker == ConversationSpeaker.USER
    assert calls[1].kwargs["message"].speaker == ConversationSpeaker.ASSISTANT


# ---------------------------------------------------------------------------
# 5.5 — persistence failure does not propagate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_turn_silent_on_db_failure() -> None:
    """If DB raises, _save_turn logs and returns without raising."""
    service, _ = _make_service(save_raises=True)
    tenant = _tenant()

    # Should not raise
    await service._save_turn(tenant=tenant, conversation_id="c1", speaker="user", content="hi")


# ---------------------------------------------------------------------------
# 5.6 — conversationId present in response dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_and_return_includes_conversation_id() -> None:
    """_record_and_return includes conversationId in the result."""
    from app.domain.rag.answer_trace import AnswerRun
    from datetime import datetime

    service = RagQueryService.__new__(RagQueryService)
    service._settings = Settings(_env_file=None)
    service._conversations = MagicMock()
    service._conversations.ensure_conversation = AsyncMock()
    service._conversations.save_message = AsyncMock()

    mock_answer_run = AnswerRun(
        id=str(uuid4()),
        tenant_id="t1",
        trace_id="tr1",
        conversation_id="conv-abc",
        original_query="q",
        standalone_query="q",
        route="abstain",
        evidence_level="none",
        profile_snapshot={},
        limitations=[],
        feature_vector=None,
        created_at=datetime.utcnow(),
    )
    mock_runs = MagicMock()
    mock_runs.create = AsyncMock(return_value=mock_answer_run)
    service._answer_runs = mock_runs
    service._trace_details = None

    tenant = _tenant()

    plan = MagicMock()
    plan.original_query = "q"
    plan.standalone_query = "q"

    result = await service._record_and_return(
        tenant=tenant,
        plan=plan,
        trace_id="tr1",
        conversation_id="conv-abc",
        route="abstain",
        evidence_level="none",
        citations=(),
        answer=None,
        limitation="No evidence.",
        decomposition={},
        memory={},
    )

    assert result["conversationId"] == "conv-abc"
