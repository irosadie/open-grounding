"""Tenant-scoped answer trace access and feedback without raw source duplication."""

from datetime import UTC, datetime, timedelta

from app.core.settings import Settings
from app.domain.audit import AuditAction
from app.domain.errors import DomainError
from app.domain.models import UserRole
from app.domain.rag.answer_trace_repositories import AnswerFeedbackRepository, AnswerRunRepository
from app.domain.tenant_context import TenantContext
from app.infrastructure.audit import record_audit_event


class RagTraceService:
    def __init__(self, settings: Settings, answer_runs: AnswerRunRepository, feedback: AnswerFeedbackRepository) -> None:
        self._settings = settings
        self._answer_runs = answer_runs
        self._feedback = feedback

    async def get_trace(self, *, tenant: TenantContext, trace_id: str) -> dict[str, object]:
        if tenant.role is not UserRole.ADMIN:
            raise DomainError.forbidden("Operator access is required to inspect answer traces")
        answer_run = await self._answer_runs.find_by_trace_id(tenant_id=tenant.tenant_id, trace_id=trace_id)
        if answer_run is None or answer_run.created_at < _retention_cutoff(self._settings):
            raise DomainError("ANSWER_TRACE_NOT_FOUND", "Answer trace not found", 404)
        record_audit_event(
            tenant_id=tenant.tenant_id,
            actor_id=tenant.user_id,
            action=AuditAction.ACCESS_GRANTED,
            resource_type="rag_answer_trace",
            resource_id=answer_run.id,
            trace_id=trace_id,
        )
        return {
            "traceId": answer_run.trace_id,
            "originalQuery": answer_run.original_query,
            "standaloneQuery": answer_run.standalone_query,
            "route": answer_run.route,
            "evidenceLevel": answer_run.evidence_level,
            "profileSnapshot": answer_run.profile_snapshot,
            "limitations": list(answer_run.limitations),
            "createdAt": answer_run.created_at.replace(tzinfo=UTC).isoformat(),
        }

    async def create_feedback(
        self,
        *,
        tenant: TenantContext,
        trace_id: str,
        rating: int | None,
        comment: str | None,
    ) -> dict[str, object]:
        answer_run = await self._answer_runs.find_by_trace_id(tenant_id=tenant.tenant_id, trace_id=trace_id)
        if answer_run is None or answer_run.created_at < _retention_cutoff(self._settings):
            raise DomainError("ANSWER_TRACE_NOT_FOUND", "Answer trace not found", 404)
        feedback = await self._feedback.create(
            tenant_id=tenant.tenant_id,
            answer_run_id=answer_run.id,
            user_id=tenant.user_id,
            rating=rating,
            comment=comment,
        )
        record_audit_event(
            tenant_id=tenant.tenant_id,
            actor_id=tenant.user_id,
            action=AuditAction.CREATE,
            resource_type="rag_answer_feedback",
            resource_id=feedback.id,
            trace_id=trace_id,
            details={"hasRating": rating is not None, "hasComment": comment is not None},
        )
        return {"id": feedback.id, "traceId": trace_id, "createdAt": feedback.created_at.replace(tzinfo=UTC).isoformat()}


def _retention_cutoff(settings: Settings) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=settings.rag_query_trace_retention_days)
