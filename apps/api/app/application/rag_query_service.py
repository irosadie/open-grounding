"""Feature-flagged query orchestration with a safe, deterministic fallback."""

from time import monotonic
from uuid import uuid4

from app.application.rag_query_admission import RagQueryAdmission
from app.core.settings import Settings
from app.domain.rag.answer_trace_repositories import AnswerRunRepository, AnswerTraceDetailRepository
from app.domain.rag.catalog import IndexGeneration, KnowledgeBaseStatus
from app.domain.rag.conversation_repositories import ConversationHistoryRepository
from app.domain.rag.policy import qdrant_policy_filter
from app.domain.rag.query import EvidenceLevel, QueryRoute, plan_query
from app.domain.rag.repositories import IndexGenerationRepository, KnowledgeBaseRepository
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_metrics import record_query_metric


class RagQueryService:
    def __init__(
        self,
        settings: Settings,
        answer_runs: AnswerRunRepository,
        admission: RagQueryAdmission,
        knowledge_bases: KnowledgeBaseRepository,
        conversations: ConversationHistoryRepository,
        generations: IndexGenerationRepository,
        trace_details: AnswerTraceDetailRepository | None = None,
    ) -> None:
        self._settings = settings
        self._answer_runs = answer_runs
        self._admission = admission
        self._knowledge_bases = knowledge_bases
        self._conversations = conversations
        self._generations = generations
        self._trace_details = trace_details

    async def query(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        conversation_id: str | None,
    ) -> dict[str, object]:
        trace_id = str(uuid4())
        started_at = monotonic()
        admitted = False
        try:
            self._admission.admit(tenant=tenant, payload_bytes=len(message.encode()))
            admitted = True
            record_query_metric(tenant_id=tenant.tenant_id, trace_id=trace_id, stage="admission", outcome="accepted", duration_ms=_duration_ms(started_at))
            result = await self._query_admitted(
                tenant=tenant,
                message=message,
                knowledge_base_ids=knowledge_base_ids,
                conversation_id=conversation_id,
                trace_id=trace_id,
            )
            _record_safe_pipeline_metrics(
                tenant_id=tenant.tenant_id,
                trace_id=trace_id,
                route=str(result["route"]),
                duration_ms=_duration_ms(started_at),
            )
            record_query_metric(tenant_id=tenant.tenant_id, trace_id=trace_id, stage="query", outcome=str(result["route"]), duration_ms=_duration_ms(started_at))
            return result
        except Exception:
            record_query_metric(tenant_id=tenant.tenant_id, trace_id=trace_id, stage="query", outcome="failed", duration_ms=_duration_ms(started_at))
            raise
        finally:
            if admitted:
                self._admission.release(tenant=tenant)

    async def _query_admitted(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        conversation_id: str | None,
        trace_id: str,
    ) -> dict[str, object]:
        recent_messages = await self._recent_messages(tenant=tenant, conversation_id=conversation_id)
        plan = plan_query(message, max_chars=self._settings.rag_query_max_message_chars, knowledge_base_ids=knowledge_base_ids)
        authorized_ids: tuple[str, ...] = ()
        generations: list[IndexGeneration] = []
        if not self._settings.rag_query_enabled:
            limitation = "Query is not enabled for this deployment."
            outcome = _safe_outcome(QueryRoute.ABSTAIN, limitation, trace_id)
        elif plan.route is not QueryRoute.GROUNDED:
            limitation = plan.reason or "Evidence is unavailable."
            outcome = _safe_outcome(plan.route, limitation, trace_id)
        else:
            authorized_ids = await self._authorized_knowledge_base_ids(tenant=tenant, knowledge_base_ids=knowledge_base_ids)
            generations = await self._generations.find_active_for_knowledge_bases(
                tenant_id=tenant.tenant_id, knowledge_base_ids=authorized_ids
            )
            if not authorized_ids:
                limitation = "No requested knowledge base is available to this tenant."
            elif not generations:
                limitation = "No active validated document generation is available."
            else:
                limitation = "No validated evidence is available yet."
            outcome = _safe_outcome(QueryRoute.ABSTAIN, limitation, trace_id)
        answer_run = await self._answer_runs.create(
            tenant_id=tenant.tenant_id,
            trace_id=trace_id,
            conversation_id=conversation_id,
            original_query=plan.original_query,
            standalone_query=plan.standalone_query,
            route=str(outcome["route"]),
            evidence_level=EvidenceLevel.NONE.value,
            profile_snapshot={
                "profileId": self._settings.rag_query_profile_id,
                "recentConversationMessageCount": len(recent_messages),
                "mandatoryFilter": qdrant_policy_filter(
                    tenant=tenant,
                    knowledge_base_ids=authorized_ids if plan.route is QueryRoute.GROUNDED and self._settings.rag_query_enabled else (),
                    active_generation_ids=tuple(generation.id for generation in generations) if plan.route is QueryRoute.GROUNDED and self._settings.rag_query_enabled else (),
                ),
            },
            limitations=(limitation,),
        )
        if self._trace_details is not None:
            await self._trace_details.create_retrieval_summary(
                tenant_id=tenant.tenant_id,
                answer_run_id=answer_run.id,
                summary={
                    "authorizedKnowledgeBaseCount": len(authorized_ids),
                    "activeGenerationCount": len(generations),
                    "retrievalExecuted": False,
                    "reason": limitation,
                },
            )
            await self._trace_details.create_validation_outcome(
                tenant_id=tenant.tenant_id,
                answer_run_id=answer_run.id,
                is_valid=True,
                checks={"release": "safe_abstention", "validationExecuted": False},
                repair_attempted=False,
            )
        return outcome

    async def _recent_messages(self, *, tenant: TenantContext, conversation_id: str | None) -> list[str]:
        if conversation_id is None:
            return []
        messages = await self._conversations.recent_messages(
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            conversation_id=conversation_id,
            limit=self._settings.rag_query_recent_messages,
        )
        return [message.content for message in messages]

    async def _authorized_knowledge_base_ids(self, *, tenant: TenantContext, knowledge_base_ids: tuple[str, ...]) -> tuple[str, ...]:
        authorized_ids: list[str] = []
        for knowledge_base_id in knowledge_base_ids:
            knowledge_base = await self._knowledge_bases.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
            if knowledge_base is not None and knowledge_base.status is KnowledgeBaseStatus.ACTIVE:
                authorized_ids.append(knowledge_base_id)
        return tuple(authorized_ids)


def _safe_outcome(route: QueryRoute, limitation: str, trace_id: str) -> dict[str, object]:
    return {
        "answer": None,
        "route": route.value,
        "evidenceLevel": EvidenceLevel.NONE.value,
        "citations": [],
        "limitations": [limitation],
        "traceId": trace_id,
    }


def _duration_ms(started_at: float) -> int:
    return int((monotonic() - started_at) * 1_000)


def _record_safe_pipeline_metrics(*, tenant_id: str, trace_id: str, route: str, duration_ms: int) -> None:
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="planning", outcome=route, duration_ms=duration_ms)
    for stage in ("retrieval", "reranking", "generation"):
        record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage=stage, outcome="skipped", duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="validation", outcome="safe_abstention", duration_ms=duration_ms)
