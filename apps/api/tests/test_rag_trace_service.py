from datetime import UTC, datetime, timedelta

import pytest

from app.application.rag_trace_service import RagTraceService
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import UserRole
from app.domain.rag.answer_trace import AnswerFeedback, AnswerRun
from app.domain.tenant_context import TenantContext


class AnswerRunsStub:
    def __init__(self, answer_run: AnswerRun | None) -> None:
        self.answer_run = answer_run
        self.request: tuple[str, str] | None = None

    async def find_by_trace_id(self, *, tenant_id: str, trace_id: str) -> AnswerRun | None:
        self.request = (tenant_id, trace_id)
        return self.answer_run


class FeedbackStub:
    def __init__(self) -> None:
        self.created: dict[str, object] | None = None

    async def create(self, **kwargs: object) -> AnswerFeedback:
        self.created = kwargs
        return AnswerFeedback("feedback-1", str(kwargs["tenant_id"]), str(kwargs["answer_run_id"]), str(kwargs["user_id"]), kwargs["rating"], kwargs["comment"], datetime.now(UTC).replace(tzinfo=None))


def _tenant(role: UserRole = UserRole.USER) -> TenantContext:
    return TenantContext(tenant_id="tenant-1", membership_id="membership-1", user_id="user-1", role=role)


def _answer_run(*, created_at: datetime | None = None) -> AnswerRun:
    return AnswerRun(
        "run-1",
        "tenant-1",
        "trace-1",
        None,
        "original",
        "standalone",
        "grounded",
        "high",
        {"profileId": "v1"},
        ("limitation",),
        created_at or datetime.now(UTC).replace(tzinfo=None),
    )


@pytest.mark.asyncio
async def test_operator_trace_access_is_tenant_scoped_and_excludes_hidden_data() -> None:
    runs = AnswerRunsStub(_answer_run())
    result = await RagTraceService(Settings(_env_file=None), runs, FeedbackStub()).get_trace(tenant=_tenant(UserRole.ADMIN), trace_id="trace-1")

    assert runs.request == ("tenant-1", "trace-1")
    assert result["profileSnapshot"] == {"profileId": "v1"}
    assert "hiddenReasoning" not in result


@pytest.mark.asyncio
async def test_non_operator_cannot_inspect_answer_trace() -> None:
    with pytest.raises(DomainError, match="Operator access"):
        await RagTraceService(Settings(_env_file=None), AnswerRunsStub(_answer_run()), FeedbackStub()).get_trace(tenant=_tenant(), trace_id="trace-1")


@pytest.mark.asyncio
async def test_feedback_requires_a_retained_answer_run_in_the_active_tenant() -> None:
    feedback = FeedbackStub()
    await RagTraceService(Settings(_env_file=None), AnswerRunsStub(_answer_run()), feedback).create_feedback(
        tenant=_tenant(), trace_id="trace-1", rating=5, comment="Helpful"
    )

    assert feedback.created == {"tenant_id": "tenant-1", "answer_run_id": "run-1", "user_id": "user-1", "rating": 5, "comment": "Helpful"}


@pytest.mark.asyncio
async def test_expired_answer_trace_is_not_accessible_or_feedback_eligible() -> None:
    old_run = _answer_run(created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=31))
    service = RagTraceService(Settings(_env_file=None, rag_query_trace_retention_days=30), AnswerRunsStub(old_run), FeedbackStub())

    with pytest.raises(DomainError, match="Answer trace not found"):
        await service.create_feedback(tenant=_tenant(), trace_id="trace-1", rating=None, comment=None)
