"""SQLAlchemy persistence for safe RAG answer-run metadata."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.rag.answer_trace import AnswerCitation, AnswerFeedback, AnswerRun
from app.infrastructure.database import Base, utc_now


class ConversationRecord(Base):
    __tablename__ = "rag_conversations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class AnswerRunRecord(Base):
    __tablename__ = "rag_answer_runs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    original_query: Mapped[str] = mapped_column(String(8_000), nullable=False)
    standalone_query: Mapped[str | None] = mapped_column(String(8_000), nullable=True)
    route: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(20), nullable=False)
    profile_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class AnswerCitationRecord(Base):
    __tablename__ = "rag_answer_citations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    answer_run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_answer_runs.id", ondelete="CASCADE"), nullable=False)
    citation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    chunk_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_chunks.id", ondelete="RESTRICT"), nullable=False)
    document_version_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="RESTRICT"), nullable=False)
    locator: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class AnswerFeedbackRecord(Base):
    __tablename__ = "rag_answer_feedback"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    answer_run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_answer_runs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(String(2_000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class RetrievalSummaryRecord(Base):
    __tablename__ = "rag_retrieval_summaries"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    answer_run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_answer_runs.id", ondelete="CASCADE"), nullable=False)
    summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class ValidationOutcomeRecord(Base):
    __tablename__ = "rag_validation_outcomes"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    answer_run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_answer_runs.id", ondelete="CASCADE"), nullable=False)
    is_valid: Mapped[bool] = mapped_column(nullable=False)
    checks: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    repair_attempted: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class EvaluationResultRecord(Base):
    __tablename__ = "rag_evaluation_results"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(120), nullable=False)
    fixture_id: Mapped[str] = mapped_column(String(120), nullable=False)
    metrics: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


def _to_answer_run(row: AnswerRunRecord) -> AnswerRun:
    return AnswerRun(row.id, row.tenant_id, row.trace_id, row.conversation_id, row.original_query, row.standalone_query, row.route, row.evidence_level, row.profile_snapshot, tuple(row.limitations), row.created_at)


def _to_answer_citation(row: AnswerCitationRecord) -> AnswerCitation:
    return AnswerCitation(row.id, row.tenant_id, row.answer_run_id, row.citation_id, row.chunk_id, row.document_version_id, row.locator, row.created_at)


def _to_answer_feedback(row: AnswerFeedbackRecord) -> AnswerFeedback:
    return AnswerFeedback(row.id, row.tenant_id, row.answer_run_id, row.user_id, row.rating, row.comment, row.created_at)


class SqlAlchemyAnswerRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
    ) -> AnswerRun:
        row = AnswerRunRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            trace_id=trace_id,
            conversation_id=conversation_id,
            original_query=original_query,
            standalone_query=standalone_query,
            route=route,
            evidence_level=evidence_level,
            profile_snapshot=profile_snapshot,
            limitations=list(limitations),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_answer_run(row)

    async def find_by_trace_id(self, *, tenant_id: str, trace_id: str) -> AnswerRun | None:
        result = await self._session.execute(select(AnswerRunRecord).where(AnswerRunRecord.tenant_id == tenant_id, AnswerRunRecord.trace_id == trace_id))
        row = result.scalar_one_or_none()
        return _to_answer_run(row) if row else None


class SqlAlchemyAnswerCitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: str,
        answer_run_id: str,
        citation_id: str,
        chunk_id: str,
        document_version_id: str,
        locator: str | None,
    ) -> AnswerCitation:
        row = AnswerCitationRecord(id=str(uuid4()), tenant_id=tenant_id, answer_run_id=answer_run_id, citation_id=citation_id, chunk_id=chunk_id, document_version_id=document_version_id, locator=locator)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_answer_citation(row)


class SqlAlchemyAnswerFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: str,
        answer_run_id: str,
        user_id: str,
        rating: int | None,
        comment: str | None,
    ) -> AnswerFeedback:
        row = AnswerFeedbackRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            answer_run_id=answer_run_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_answer_feedback(row)


class SqlAlchemyAnswerTraceDetailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_retrieval_summary(self, *, tenant_id: str, answer_run_id: str, summary: dict[str, object]) -> None:
        self._session.add(RetrievalSummaryRecord(id=str(uuid4()), tenant_id=tenant_id, answer_run_id=answer_run_id, summary=summary))
        await self._session.commit()

    async def create_validation_outcome(
        self, *, tenant_id: str, answer_run_id: str, is_valid: bool, checks: dict[str, object], repair_attempted: bool
    ) -> None:
        self._session.add(
            ValidationOutcomeRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                answer_run_id=answer_run_id,
                is_valid=is_valid,
                checks=checks,
                repair_attempted=repair_attempted,
            )
        )
        await self._session.commit()


class SqlAlchemyEvaluationResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, *, tenant_id: str, profile_id: str, fixture_id: str, metrics: dict[str, float]) -> None:
        result = await self._session.execute(
            select(EvaluationResultRecord).where(
                EvaluationResultRecord.tenant_id == tenant_id,
                EvaluationResultRecord.profile_id == profile_id,
                EvaluationResultRecord.fixture_id == fixture_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = EvaluationResultRecord(id=str(uuid4()), tenant_id=tenant_id, profile_id=profile_id, fixture_id=fixture_id, metrics=metrics)
            self._session.add(row)
        else:
            row.metrics = metrics
        await self._session.commit()

    async def has_passing_result(self, *, tenant_id: str, profile_id: str) -> bool:
        result = await self._session.execute(
            select(EvaluationResultRecord.metrics).where(
                EvaluationResultRecord.tenant_id == tenant_id,
                EvaluationResultRecord.profile_id == profile_id,
            )
        )
        return any(
            metrics.get("retrievalRecall") == 1.0
            and metrics.get("citationCorrectness") == 1.0
            and metrics.get("citationCoverage") == 1.0
            and metrics.get("groundedness") == 1.0
            and metrics.get("abstentionQuality") == 1.0
            and metrics.get("failureRate") == 0.0
            for metrics in result.scalars()
        )
