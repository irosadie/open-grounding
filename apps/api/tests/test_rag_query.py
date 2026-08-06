from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.rag_query_admission import RagQueryAdmission
from app.application.rag_query_service import RagQueryService
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import UserRole
from app.domain.rag.answer_trace import AnswerRun
from app.domain.rag.catalog import KnowledgeBase
from app.domain.rag.conversation import ConversationMessage
from app.domain.rag.query import QueryRoute, normalize_query, plan_query
from app.domain.tenant_context import TenantContext
from app.interfaces.http.schemas import RagQueryRequest, RagQueryStreamRequest


@pytest.mark.parametrize("field_name", ["tenant_id", "acl_principals", "clearance", "active_generation_ids", "filter"])
def test_query_request_rejects_client_security_scope(field_name: str) -> None:
    with pytest.raises(ValidationError, match=field_name):
        RagQueryRequest(message="hello", knowledge_base_ids=["kb"], **{field_name: "attacker"})


def test_stream_contract_is_explicit_and_cannot_be_disabled() -> None:
    stream_request = RagQueryStreamRequest(message="hello", knowledge_base_ids=["kb"])
    assert stream_request.stream is True
    with pytest.raises(ValidationError):
        RagQueryStreamRequest(message="hello", knowledge_base_ids=["kb"], stream=False)


def test_query_plan_clarifies_empty_message_and_abstains_without_knowledge_base() -> None:
    assert plan_query("  ", max_chars=10, knowledge_base_ids=("kb",)).route is QueryRoute.CLARIFY
    assert plan_query("question", max_chars=10, knowledge_base_ids=()).route is QueryRoute.ABSTAIN


def test_query_normalization_preserves_original_trace_and_bounds_standalone_query() -> None:
    original = "  What\u00a0is   \uff26\uff2f\uff2f?  "
    plan = plan_query(original, max_chars=12, knowledge_base_ids=("kb",))
    assert plan.original_query == original
    assert plan.standalone_query == "What is FOO?"
    assert normalize_query("one two three", max_chars=7) == "one two"


def test_query_normalization_is_bounded_after_whitespace_collapse() -> None:
    assert normalize_query("  alpha   beta  gamma ", max_chars=10) == "alpha beta"


@pytest.mark.asyncio
async def test_disabled_query_is_safe_abstention() -> None:
    tenant = TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )
    answer_runs = FakeAnswerRunRepository()
    settings = Settings(_env_file=None)
    result = await RagQueryService(settings, answer_runs, RagQueryAdmission(settings), FakeKnowledgeBaseRepository(), FakeConversationHistoryRepository(), FakeIndexGenerationRepository()).query(
        tenant=tenant, message="question", knowledge_base_ids=("kb",), conversation_id=None
    )
    assert result["route"] == "abstain"
    assert result["citations"] == []
    assert answer_runs.created["tenant_id"] == tenant.tenant_id
    assert answer_runs.created["original_query"] == "question"


@pytest.mark.asyncio
async def test_enabled_query_abstains_when_knowledge_base_is_not_tenant_available() -> None:
    tenant = TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )
    settings = Settings(_env_file=None, rag_query_enabled=True)
    result = await RagQueryService(settings, FakeAnswerRunRepository(), RagQueryAdmission(settings), FakeKnowledgeBaseRepository(), FakeConversationHistoryRepository(), FakeIndexGenerationRepository()).query(
        tenant=tenant, message="question", knowledge_base_ids=("unavailable",), conversation_id=None
    )
    assert result["limitations"] == ["No requested knowledge base is available to this tenant."]


@pytest.mark.asyncio
async def test_query_uses_only_configured_recent_conversation_window() -> None:
    tenant = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)
    settings = Settings(_env_file=None, rag_query_recent_messages=2)
    conversations = FakeConversationHistoryRepository()
    await RagQueryService(settings, FakeAnswerRunRepository(), RagQueryAdmission(settings), FakeKnowledgeBaseRepository(), conversations, FakeIndexGenerationRepository()).query(
        tenant=tenant, message="question", knowledge_base_ids=("kb",), conversation_id="conversation-1"
    )
    assert conversations.request == (tenant.tenant_id, tenant.user_id, "conversation-1", 2)


@pytest.mark.asyncio
async def test_query_persists_bounded_retrieval_and_validation_trace_outcomes() -> None:
    tenant = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)
    trace_details = FakeAnswerTraceDetailRepository()
    await RagQueryService(
        Settings(_env_file=None, rag_query_enabled=True),
        FakeAnswerRunRepository(),
        RagQueryAdmission(Settings(_env_file=None, rag_query_enabled=True)),
        FakeKnowledgeBaseRepository(),
        FakeConversationHistoryRepository(),
        FakeIndexGenerationRepository(),
        trace_details,
    ).query(tenant=tenant, message="question", knowledge_base_ids=("kb",), conversation_id=None)

    assert trace_details.retrieval_summary == {
        "route": "abstain",
        "reason": "No requested knowledge base is available to this tenant.",
        "decomposition": {
            "triggered": False,
            "complexity_score": 0.0,
            "reason": "not_configured",
        },
        "memory": {
            "triggered": False,
            "chunks_retrieved": 0,
        },
    }
    assert trace_details.validation_outcome == {"release": "abstain", "validationExecuted": False}


def test_query_admission_enforces_payload_rate_and_concurrency_limits() -> None:
    tenant = TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )
    settings = Settings(_env_file=None, rag_query_max_payload_bytes=3, rag_query_requests_per_minute=1, rag_query_max_concurrency=1)
    admission = RagQueryAdmission(settings)
    with pytest.raises(DomainError, match="QUERY_PAYLOAD_TOO_LARGE"):
        admission.admit(tenant=tenant, payload_bytes=4)
    admission.admit(tenant=tenant, payload_bytes=3)
    with pytest.raises(DomainError, match="QUERY_RATE_LIMITED"):
        admission.admit(tenant=tenant, payload_bytes=3)
    admission.release(tenant=tenant)


class FakeAnswerRunRepository:
    def __init__(self) -> None:
        self.created: dict[str, object] = {}

    async def create(self, **kwargs: object) -> AnswerRun:
        self.created = kwargs
        return AnswerRun(
            id=str(uuid4()),
            tenant_id=str(kwargs["tenant_id"]),
            trace_id=str(kwargs["trace_id"]),
            conversation_id=None,
            original_query=str(kwargs["original_query"]),
            standalone_query=None,
            route=str(kwargs["route"]),
            evidence_level=str(kwargs["evidence_level"]),
            profile_snapshot={},
            limitations=(),
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )

    async def find_by_trace_id(self, *, tenant_id: str, trace_id: str) -> AnswerRun | None:
        del tenant_id, trace_id
        return None


class FakeKnowledgeBaseRepository:
    async def find_by_id(self, *, tenant_id: str, knowledge_base_id: str) -> KnowledgeBase | None:
        del tenant_id, knowledge_base_id
        return None

    async def create(self, *, tenant_id: str, slug: str, name: str, status: str) -> KnowledgeBase:
        del tenant_id, slug, name, status
        raise AssertionError("not used")


class FakeConversationHistoryRepository:
    def __init__(self) -> None:
        self.request: tuple[str, str, str, int] | None = None

    async def recent_messages(self, *, tenant_id: str, user_id: str, conversation_id: str, limit: int) -> list[ConversationMessage]:
        self.request = (tenant_id, user_id, conversation_id, limit)
        return []


class FakeIndexGenerationRepository:
    async def find_active_for_knowledge_bases(self, *, tenant_id: str, knowledge_base_ids: tuple[str, ...]) -> list[object]:
        del tenant_id, knowledge_base_ids
        return []


class FakeAnswerTraceDetailRepository:
    def __init__(self) -> None:
        self.retrieval_summary: dict[str, object] = {}
        self.validation_outcome: dict[str, object] = {}

    async def create_retrieval_summary(self, *, tenant_id: str, answer_run_id: str, summary: dict[str, object]) -> None:
        del tenant_id, answer_run_id
        self.retrieval_summary = summary

    async def create_validation_outcome(
        self, *, tenant_id: str, answer_run_id: str, is_valid: bool, checks: dict[str, object], repair_attempted: bool
    ) -> None:
        del tenant_id, answer_run_id
        assert is_valid is True
        assert repair_attempted is False
        self.validation_outcome = checks
