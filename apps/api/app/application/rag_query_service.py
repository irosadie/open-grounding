"""Grounded query orchestration: plan → retrieve → evidence → generate → trace.

Feature-flagged by ``rag_query_enabled``. On any gate failure the service falls
back to a safe abstention, never an ungrounded answer.
"""

from __future__ import annotations

import asyncio
import logging
from time import monotonic
from typing import TYPE_CHECKING
from uuid import uuid4

from app.application.evidence_merger import merge_evidence
from app.application.rag_generation import RagGenerationService
from app.application.rag_hybrid_retrieval import RagHybridRetrievalService
from app.application.rag_query_admission import RagQueryAdmission
from app.core.settings import Settings
from app.domain.rag.answer import GroundedAnswer
from app.domain.rag.answer_trace_repositories import AnswerRunRepository, AnswerTraceDetailRepository
from app.domain.rag.catalog import IndexGeneration, KnowledgeBaseStatus
from app.domain.rag.complexity_scorer import score as complexity_score
from app.domain.rag.conversation_repositories import ConversationHistoryRepository
from app.domain.rag.evidence import EvidenceChunk, build_evidence_context
from app.domain.rag.policy import qdrant_policy_filter
from app.domain.rag.query import EvidenceDecision, EvidenceLevel, QueryRoute, gate_evidence, plan_query
from app.domain.rag.repositories import (
    DecompositionConfigRepository,
    IndexGenerationRepository,
    IndexProfileRepository,
    KnowledgeBaseRepository,
)
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_metrics import record_query_metric

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


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
        decomposition_configs: DecompositionConfigRepository | None = None,
        index_profiles: IndexProfileRepository | None = None,
        retrieval: RagHybridRetrievalService | None = None,
        generation: RagGenerationService | None = None,
    ) -> None:
        self._settings = settings
        self._answer_runs = answer_runs
        self._admission = admission
        self._knowledge_bases = knowledge_bases
        self._conversations = conversations
        self._generations = generations
        self._trace_details = trace_details
        self._decomposition_configs = decomposition_configs
        self._index_profiles = index_profiles
        self._retrieval = retrieval
        self._generation = generation

    async def query(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        conversation_id: str | None,
        decomposition_enabled: bool | None = None,
        decomposition_max_sub_queries: int | None = None,
        memory_enabled: bool | None = None,
        session: "AsyncSession | None" = None,
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
                decomposition_enabled=decomposition_enabled,
                decomposition_max_sub_queries=decomposition_max_sub_queries,
                memory_enabled=memory_enabled,
                session=session,
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
        decomposition_enabled: bool | None,
        decomposition_max_sub_queries: int | None,
        memory_enabled: bool | None,
        session: "AsyncSession | None",
    ) -> dict[str, object]:
        plan = plan_query(message, max_chars=self._settings.rag_query_max_message_chars, knowledge_base_ids=knowledge_base_ids)

        # Load recent conversation messages (for context + window test)
        await self._recent_messages(tenant=tenant, conversation_id=conversation_id)

        memory_meta = await self._retrieve_memory(
            tenant=tenant, message=message, knowledge_base_ids=knowledge_base_ids,
            memory_enabled=memory_enabled, session=session,
        )
        decomposition_meta = await self._compute_decomposition_meta(
            tenant=tenant, message=message, knowledge_base_ids=knowledge_base_ids,
            decomposition_enabled=decomposition_enabled, decomposition_max_sub_queries=decomposition_max_sub_queries,
        )

        if not self._settings.rag_query_enabled:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation="Query is not enabled for this deployment.",
                decomposition=decomposition_meta, memory=memory_meta,
            )
        if plan.route is not QueryRoute.GROUNDED:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation=plan.reason or "Evidence is unavailable.",
                decomposition=decomposition_meta, memory=memory_meta,
            )

        authorized_ids = await self._authorized_knowledge_base_ids(tenant=tenant, knowledge_base_ids=knowledge_base_ids)
        if not authorized_ids:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation="No requested knowledge base is available to this tenant.",
                decomposition=decomposition_meta, memory=memory_meta,
            )

        generations = await self._generations.find_active_for_knowledge_bases(
            tenant_id=tenant.tenant_id, knowledge_base_ids=authorized_ids
        )
        if not generations:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation="No active validated document generation is available.",
                decomposition=decomposition_meta, memory=memory_meta,
            )

        return await self._run_grounded(
            tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
            authorized_ids=authorized_ids, generations=generations,
            decomposition_meta=decomposition_meta, memory_meta=memory_meta,
        )

    async def _run_grounded(
        self,
        *,
        tenant: TenantContext,
        plan: object,
        trace_id: str,
        conversation_id: str | None,
        authorized_ids: tuple[str, ...],
        generations: list[IndexGeneration],
        decomposition_meta: dict[str, object],
        memory_meta: dict[str, object],
    ) -> dict[str, object]:
        """Execute retrieval + generation. Returns grounded answer or abstain fallback."""
        active_generation_ids = tuple(generation.id for generation in generations)
        collection = self._settings.rag_query_profile_id or "rag"

        # Resolve retrieval profile from active index profile
        embedding_profile_id: str | None = None
        sparse_profile_id: str | None = None
        if self._index_profiles:
            index_profile = await self._index_profiles.find_active(tenant_id=tenant.tenant_id)
            if index_profile is not None:
                embedding_profile_id = index_profile.embedding_profile_id
                sparse_profile_id = index_profile.sparse_profile_id
                collection = index_profile.collection or collection

        if embedding_profile_id is None:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation="No active index profile with an embedding model is available.",
                decomposition=decomposition_meta, memory=memory_meta,
            )

        query_text = getattr(plan, "standalone_query", None) or getattr(plan, "original_query", "")
        questions = [query_text]
        # If decomposition triggered, use sub-queries
        if decomposition_meta.get("triggered") and self._decomposition_configs and authorized_ids:
            sub_queries = await self._decompose(
                tenant=tenant, message=query_text, knowledge_base_id=authorized_ids[0],
            )
            if sub_queries:
                questions = sub_queries

        # Parallel retrieval across sub-queries
        dense_results: list[list[dict[str, object]]] = []
        sparse_results: list[list[dict[str, object]]] = []
        if self._retrieval:
            results = await asyncio.gather(
                *[
                    self._retrieval.retrieve(
                        tenant=tenant,
                        query=q,
                        collection=collection,
                        knowledge_base_ids=authorized_ids,
                        active_generation_ids=active_generation_ids,
                        embedding_profile_id=embedding_profile_id,
                        sparse_profile_id=sparse_profile_id,
                    )
                    for q in questions
                ],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    logger.warning("Retrieval failed: %s", r)
                    continue
                dense, sparse = r
                dense_results.append(dense)
                sparse_results.append(sparse)

        merged, dedup_removed = merge_evidence([*dense_results, *sparse_results], top_k=self._settings.rag_context_max_chunks)

        if not merged:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation="No validated evidence is available yet.",
                decomposition=decomposition_meta, memory=memory_meta,
            )

        # Build evidence context
        evidence_chunks = _to_evidence_chunks(merged, tenant_id=tenant.tenant_id)
        context = build_evidence_context(
            chunks=evidence_chunks,
            tenant_id=tenant.tenant_id,
            active_generation_ids=active_generation_ids,
            token_budget=self._settings.rag_context_token_budget,
            output_reserve=self._settings.rag_generation_max_output_tokens,
        )

        # Gate evidence
        decision = gate_evidence(
            candidate_count=len(merged),
            independent_source_count=_independent_sources(merged),
            top_score=_top_score(merged),
            retry_attempted=False,
        )
        if decision.route is not QueryRoute.GROUNDED:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation="Evidence quality is insufficient to answer this question.",
                decomposition=decomposition_meta, memory=memory_meta, decision=decision,
            )

        # Memory injection as supplementary context
        supplementary = None
        memory_block = (memory_meta or {}).get("context_block")
        if memory_block:
            supplementary = memory_block

        # Generate
        if self._generation is None:
            return await self._finish_abstain(
                tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
                limitation="Generation is not configured.",
                decomposition=decomposition_meta, memory=memory_meta,
            )

        generation_profile_id = self._settings.rag_query_profile_id or "default-v1"
        answer = await self._generation.generate(
            tenant=tenant,
            question=query_text,
            evidence=context,
            profile_id=generation_profile_id,
            supplementary=supplementary,
        )

        return await self._finish_grounded(
            tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
            authorized_ids=authorized_ids, generations=generations,
            answer=answer, context=context, decision=decision,
            decomposition=decomposition_meta, memory=memory_meta,
        )

    async def _decompose(self, *, tenant: TenantContext, message: str, knowledge_base_id: str) -> list[str]:
        """Run the LLM decomposer for a configured KB. Returns [] on failure/fallback."""
        try:
            from app.application.query_decomposer import QueryDecomposer
            from app.infrastructure.rag_catalog import SqlAlchemyModelProfileRepository
            from app.infrastructure.database import create_session_factory

            if not self._decomposition_configs:
                return []
            config = await self._decomposition_configs.find_by_knowledge_base(
                tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id
            )
            if config is None or not config.enabled:
                return []

            session_factory = create_session_factory(self._settings)
            async with session_factory() as session:
                profile_repo = SqlAlchemyModelProfileRepository(session)
                model_profile = await profile_repo.find_by_id(
                    tenant_id=tenant.tenant_id, profile_id=config.model_profile_id
                )
                if model_profile is None:
                    return []
                kb_name = knowledge_base_id
                decomposer = QueryDecomposer(self._settings)
                result = await decomposer.decompose(
                    query=message,
                    config=config,
                    knowledge_base_name=kb_name,
                    model_profile=model_profile,
                    session=session,
                )
            return result.sub_queries if not result.fallback else []
        except Exception as e:
            logger.warning("Decomposition skipped: %s", e)
            return []

    async def _finish_abstain(
        self,
        *,
        tenant: TenantContext,
        plan: object,
        trace_id: str,
        conversation_id: str | None,
        limitation: str,
        decomposition: dict[str, object],
        memory: dict[str, object],
        decision: EvidenceDecision | None = None,
    ) -> dict[str, object]:
        return await self._record_and_return(
            tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
            route=QueryRoute.ABSTAIN.value, evidence_level=EvidenceLevel.NONE.value,
            citations=(), answer=None, limitation=limitation,
            decomposition=decomposition, memory=memory,
        )

    async def _finish_grounded(
        self,
        *,
        tenant: TenantContext,
        plan: object,
        trace_id: str,
        conversation_id: str | None,
        authorized_ids: tuple[str, ...],
        generations: list[IndexGeneration],
        answer: GroundedAnswer,
        context: object,
        decision: EvidenceDecision,
        decomposition: dict[str, object],
        memory: dict[str, object],
    ) -> dict[str, object]:
        citations = [_citation_dto(c) for c in context.citations]  # type: ignore[union-attr]
        answer_text = _render_answer(answer)
        return await self._record_and_return(
            tenant=tenant, plan=plan, trace_id=trace_id, conversation_id=conversation_id,
            route=QueryRoute.GROUNDED.value, evidence_level=decision.level.value,
            citations=tuple(citations), answer=answer_text, limitation=None,
            decomposition=decomposition, memory=memory,
        )

    async def _record_and_return(
        self,
        *,
        tenant: TenantContext,
        plan: object,
        trace_id: str,
        conversation_id: str | None,
        route: str,
        evidence_level: str,
        citations: tuple[dict[str, object], ...],
        answer: str | None,
        limitation: str | None,
        decomposition: dict[str, object],
        memory: dict[str, object],
    ) -> dict[str, object]:
        limitations = [limitation] if limitation else []
        answer_run = await self._answer_runs.create(
            tenant_id=tenant.tenant_id,
            trace_id=trace_id,
            conversation_id=conversation_id,
            original_query=getattr(plan, "original_query", ""),
            standalone_query=getattr(plan, "standalone_query", ""),
            route=route,
            evidence_level=evidence_level,
            profile_snapshot={
                "profileId": self._settings.rag_query_profile_id,
                "mandatoryFilter": qdrant_policy_filter(
                    tenant=tenant, knowledge_base_ids=(), active_generation_ids=(),
                ),
            },
            limitations=limitations,
        )
        if self._trace_details is not None:
            await self._trace_details.create_retrieval_summary(
                tenant_id=tenant.tenant_id,
                answer_run_id=answer_run.id,
                summary={
                    "route": route,
                    "reason": limitation,
                    "decomposition": decomposition,
                    "memory": {
                        "triggered": (memory or {}).get("triggered", False),
                        "chunks_retrieved": (memory or {}).get("chunks_retrieved", 0),
                    },
                },
            )
            await self._trace_details.create_validation_outcome(
                tenant_id=tenant.tenant_id,
                answer_run_id=answer_run.id,
                is_valid=True,
                checks={"release": route, "validationExecuted": False},
                repair_attempted=False,
            )
        return {
            "answer": answer,
            "route": route,
            "evidenceLevel": evidence_level,
            "citations": list(citations),
            "limitations": limitations,
            "traceId": trace_id,
            "decomposition": decomposition,
            "memory": {
                "triggered": (memory or {}).get("triggered", False),
                "chunks_retrieved": (memory or {}).get("chunks_retrieved", 0),
                "oldest_memory_age_days": (memory or {}).get("oldest_memory_age_days"),
            },
        }

    async def _compute_decomposition_meta(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        decomposition_enabled: bool | None,
        decomposition_max_sub_queries: int | None,
    ) -> dict[str, object]:
        score = complexity_score(message)
        if decomposition_enabled is False:
            return {"triggered": False, "complexity_score": score, "reason": "disabled_by_request"}
        config = None
        if self._decomposition_configs and knowledge_base_ids:
            try:
                config = await self._decomposition_configs.find_by_knowledge_base(
                    tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_ids[0]
                )
            except Exception:
                pass
        if config is None or not config.enabled:
            return {"triggered": False, "complexity_score": score, "reason": "not_configured" if config is None else "disabled_in_config"}
        if score < config.min_complexity_score:
            return {"triggered": False, "complexity_score": score, "reason": "score_below_threshold", "threshold": config.min_complexity_score}
        max_sub_queries = decomposition_max_sub_queries or config.max_sub_queries
        return {"triggered": True, "complexity_score": score, "config_id": config.id, "max_sub_queries": max_sub_queries}

    async def _recent_messages(self, *, tenant: TenantContext, conversation_id: str | None) -> list[str]:
        if conversation_id is None:
            return []
        messages = await self._conversations.recent_messages(
            tenant_id=tenant.tenant_id, user_id=tenant.user_id,
            conversation_id=conversation_id, limit=self._settings.rag_query_recent_messages,
        )
        return [message.content for message in messages]

    async def _authorized_knowledge_base_ids(self, *, tenant: TenantContext, knowledge_base_ids: tuple[str, ...]) -> tuple[str, ...]:
        authorized: list[str] = []
        for knowledge_base_id in knowledge_base_ids:
            knowledge_base = await self._knowledge_bases.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
            if knowledge_base is not None and knowledge_base.status is KnowledgeBaseStatus.ACTIVE:
                authorized.append(knowledge_base_id)
        return tuple(authorized)

    async def _retrieve_memory(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        memory_enabled: bool | None,
        session: "AsyncSession | None",
    ) -> dict[str, object]:
        empty = {"triggered": False, "chunks_retrieved": 0, "oldest_memory_age_days": None, "context_block": None}
        if memory_enabled is False or session is None or not knowledge_base_ids:
            return empty
        try:
            from app.application.memory_retriever import MemoryRetriever
            retriever = MemoryRetriever(self._settings)
            return await retriever.retrieve(
                query=message, tenant_id=tenant.tenant_id,
                knowledge_base_id=knowledge_base_ids[0], user_id=tenant.user_id, session=session,
            )
        except Exception as e:
            logger.warning("Memory retrieval skipped: %s", e)
            return empty


def _to_evidence_chunks(points: list[dict[str, object]], *, tenant_id: str) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for point in points:
        payload = point.get("payload", {}) if isinstance(point, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        chunk_id = str(payload.get("chunk_id") or point.get("id") or "")
        if not chunk_id:
            continue
        text = str(payload.get("text") or "")
        if not text:
            continue
        chunks.append(
            EvidenceChunk(
                chunk_id=chunk_id,
                tenant_id=str(payload.get("tenant_id") or tenant_id),
                document_version_id=str(payload.get("document_version_id") or ""),
                generation_id=str(payload.get("generation_id") or ""),
                title=str(payload.get("title") or "Source"),
                locator=str(payload.get("chunk_index")),
                text=text,
                token_count=max(1, len(text.split())),
                checksum=None,
            )
        )
    return chunks


def _independent_sources(points: list[dict[str, object]]) -> int:
    versions = {
        str((point.get("payload") or {}).get("document_version_id") or "")
        for point in points if isinstance(point, dict)
    }
    return len([v for v in versions if v])


def _top_score(points: list[dict[str, object]]) -> float | None:
    scores = [float(point.get("score", 0.0)) for point in points if isinstance(point, dict)]
    return max(scores) if scores else None


def _citation_dto(citation: object) -> dict[str, object]:
    return {
        "citationId": getattr(citation, "citation_id", ""),
        "chunkId": getattr(citation, "chunk_id", ""),
        "documentVersionId": getattr(citation, "document_version_id", ""),
        "title": getattr(citation, "title", ""),
        "snippet": getattr(citation, "snippet", ""),
    }


def _render_answer(answer: GroundedAnswer) -> str:
    parts: list[str] = []
    if answer.facts:
        parts.append("\n".join(f"- {claim.text}" for claim in answer.facts))
    if answer.inferences:
        parts.append("\n\nInferences:\n" + "\n".join(f"- {claim.text}" for claim in answer.inferences))
    if answer.conflicts:
        parts.append("\n\nConflicts:\n" + "\n".join(f"- {c}" for c in answer.conflicts))
    if answer.limitations:
        parts.append("\n\nLimitations:\n" + "\n".join(f"- {l}" for l in answer.limitations))
    return "\n".join(parts) if parts else "No answer could be generated."


def _duration_ms(started_at: float) -> int:
    return int((monotonic() - started_at) * 1_000)


def _record_safe_pipeline_metrics(*, tenant_id: str, trace_id: str, route: str, duration_ms: int) -> None:
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="planning", outcome=route, duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="retrieval", outcome="skipped", duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="reranking", outcome="skipped", duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="generation", outcome="skipped", duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="validation", outcome="safe_abstention", duration_ms=duration_ms)
