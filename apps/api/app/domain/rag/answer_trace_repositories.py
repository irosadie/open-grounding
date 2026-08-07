from typing import Protocol

from app.domain.rag.answer_trace import AnswerCitation, AnswerFeedback, AnswerRun


class AnswerRunRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: str,
        trace_id: str,
        conversation_id: str | None,
        original_query: str,
        standalone_query: str | None,
        route: str,
        evidence_level: str,
        profile_snapshot: dict[str, object],
        limitations: tuple[str, ...],
        feature_vector: dict[str, float] | None = None,
    ) -> AnswerRun: ...

    async def find_by_trace_id(self, *, tenant_id: str, trace_id: str) -> AnswerRun | None: ...
    async def find_by_id(self, *, tenant_id: str, answer_run_id: str) -> AnswerRun | None: ...
    async def set_feature_vector(self, *, tenant_id: str, answer_run_id: str, feature_vector: dict[str, float]) -> AnswerRun | None: ...
    async def list_unlabeled_for_profile(self, *, tenant_id: str, retrieval_profile_id: str, page: int, page_size: int) -> list[AnswerRun]: ...


class AnswerCitationRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: str,
        answer_run_id: str,
        citation_id: str,
        chunk_id: str,
        document_version_id: str,
        locator: str | None,
    ) -> AnswerCitation: ...


class AnswerFeedbackRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: str,
        answer_run_id: str,
        user_id: str,
        rating: int | None,
        comment: str | None,
    ) -> AnswerFeedback: ...


class AnswerTraceDetailRepository(Protocol):
    async def create_retrieval_summary(self, *, tenant_id: str, answer_run_id: str, summary: dict[str, object]) -> None: ...

    async def create_validation_outcome(
        self, *, tenant_id: str, answer_run_id: str, is_valid: bool, checks: dict[str, object], repair_attempted: bool
    ) -> None: ...
