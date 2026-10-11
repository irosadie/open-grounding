"""LLM-first query orchestration: plan → guardrails → retrieve → generate → trace.

Feature-flagged by ``rag_query_enabled``. Retrieval evidence controls provenance
and citations; it does not prevent a safe LLM answer when evidence is absent.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC
from time import monotonic
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from app.application.answer_policy_service import AnswerPolicyService
from app.application.evidence_merger import merge_evidence
from app.application.mcp_runtime_service import McpRuntimeService
from app.application.query_planner import QueryPlanner
from app.application.rag_answer_validation import RagAnswerValidationService
from app.application.rag_generation import RagGenerationService
from app.application.rag_hybrid_retrieval import RagHybridRetrievalService
from app.application.rag_query_admission import RagQueryAdmission
from app.application.task_executor import TaskExecutor
from app.application.task_resumer import TaskResumer
from app.core.dev_trace import get_tracer
from app.core.llm_rollout_trace import get_rollout_trace, rollout_context
from app.core.settings import Settings
from app.domain.models import NoEvidenceAction, PolicyScope
from app.domain.rag.answer import GroundedAnswer
from app.domain.rag.answer_policy import AnswerBehaviorProfile, EffectiveAnswerPolicy, GuardrailProfile
from app.domain.rag.answer_trace_repositories import AnswerRunRepository, AnswerTraceDetailRepository
from app.domain.rag.answer_validation import AnswerValidation
from app.domain.rag.catalog import IndexGeneration, KnowledgeBaseStatus
from app.domain.rag.complexity_scorer import score as complexity_score
from app.domain.rag.confidence import ConfidenceFeatureExtractor, ConfidenceScorer
from app.domain.rag.conversation_repositories import ConversationHistoryRepository
from app.domain.rag.evidence import EvidenceChunk, EvidenceContext, append_mcp_evidence, build_evidence_context
from app.domain.rag.guardrails import evaluate_answer, evaluate_query
from app.domain.rag.policy import qdrant_policy_filter
from app.domain.rag.query import EvidenceDecision, EvidenceLevel, QueryPlan, QueryRoute, gate_evidence, plan_query
from app.domain.rag.repositories import (
    DecompositionConfigRepository,
    IndexGenerationRepository,
    IndexProfileRepository,
    KnowledgeBaseRepository,
    PlannerConfigRepository,
)
from app.domain.rag.task_plan import TaskSpec, TaskType
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_metrics import record_query_metric

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], Awaitable[None]]


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
        planner_configs: PlannerConfigRepository | None = None,
        mcp_runtime: McpRuntimeService | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
        feature_extractor: ConfidenceFeatureExtractor | None = None,
        answer_policy: AnswerPolicyService | None = None,
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
        self._planner_configs = planner_configs
        self._mcp_runtime = mcp_runtime
        self._confidence_scorer = confidence_scorer
        self._feature_extractor = feature_extractor or ConfidenceFeatureExtractor()
        self._answer_policy = answer_policy
        self._answer_validation = RagAnswerValidationService()

    async def _resolve_effective_policy(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_ids: tuple[str, ...],
        project_id: str | None = None,
    ) -> EffectiveAnswerPolicy:
        if self._answer_policy is not None and (knowledge_base_ids or project_id is not None):
            return await self._answer_policy.resolve_effective(
                tenant=tenant,
                knowledge_base_ids=knowledge_base_ids,
                project_id=project_id,
            )
        return EffectiveAnswerPolicy(
            answer_behavior=AnswerBehaviorProfile(version="runtime-default-v1", scope=PolicyScope.DEPLOYMENT),
            guardrails=GuardrailProfile.platform_baseline(),
        )

    async def query(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        project_id: str | None = None,
        conversation_id: str | None,
        decomposition_enabled: bool | None = None,
        decomposition_max_sub_queries: int | None = None,
        planner_enabled: bool | None = None,
        planner_max_tasks: int | None = None,
        planner_task_types: tuple[str, ...] | None = None,
        memory_enabled: bool | None = None,
        session: AsyncSession | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, object]:
        trace_id = str(uuid4())
        started_at = monotonic()
        admitted = False
        async with rollout_context(
            trace_id=trace_id,
            source="rag.query",
            trace_dir=self._settings.rag_llm_trace_dir,
            enabled=self._settings.rag_llm_trace_enabled,
            metadata={
                "conversation_id": conversation_id,
                "knowledge_base_ids": list(knowledge_base_ids),
                "project_id": project_id,
            },
        ):
            rollout = get_rollout_trace()
            rollout.record(
                "turn_started",
                {
                    "messageHash": _message_hash(message),
                    "messageChars": len(message),
                    "knowledge_base_ids": list(knowledge_base_ids),
                    "project_id": project_id,
                },
                turn_id=trace_id,
            )
            try:
                self._admission.admit(tenant=tenant, payload_bytes=len(message.encode()))
                admitted = True
                record_query_metric(tenant_id=tenant.tenant_id, trace_id=trace_id, stage="admission", outcome="accepted", duration_ms=_duration_ms(started_at))
                result = await self._query_admitted(
                    tenant=tenant,
                    message=message,
                    knowledge_base_ids=knowledge_base_ids,
                    project_id=project_id,
                    conversation_id=conversation_id,
                    trace_id=trace_id,
                    decomposition_enabled=decomposition_enabled,
                    decomposition_max_sub_queries=decomposition_max_sub_queries,
                    planner_enabled=planner_enabled,
                    planner_max_tasks=planner_max_tasks,
                    planner_task_types=planner_task_types,
                    memory_enabled=memory_enabled,
                    session=session,
                    on_progress=on_progress,
                )
                record_query_metric(tenant_id=tenant.tenant_id, trace_id=trace_id, stage="query", outcome=str(result["route"]), duration_ms=_duration_ms(started_at))
                completed_conversation_id = result.get("conversationId")
                if result.get("route") != QueryRoute.REFUSED.value:
                    await self._enqueue_memory_summarization(
                        tenant=tenant,
                        conversation_id=completed_conversation_id if isinstance(completed_conversation_id, str) else None,
                        knowledge_base_ids=knowledge_base_ids,
                        project_id=project_id,
                        memory_enabled=memory_enabled,
                        session=session,
                    )
                rollout.record("turn_completed", {"route": result.get("route"), "conversation_id": result.get("conversationId")}, turn_id=trace_id)
                return result
            except Exception as error:
                rollout.record("turn_failed", {"error_type": type(error).__name__, "error": str(error)}, turn_id=trace_id)
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
        project_id: str | None = None,
        conversation_id: str | None,
        trace_id: str,
        decomposition_enabled: bool | None,
        decomposition_max_sub_queries: int | None,
        planner_enabled: bool | None,
        planner_max_tasks: int | None,
        planner_task_types: tuple[str, ...] | None,
        memory_enabled: bool | None,
        session: AsyncSession | None,
        on_progress: ProgressCallback | None,
    ) -> dict[str, object]:
        # Generate conversation_id server-side if not provided
        if conversation_id is None:
            conversation_id = str(uuid4())

        effective_policy = await self._resolve_effective_policy(
            tenant=tenant,
            knowledge_base_ids=knowledge_base_ids,
            project_id=project_id,
        )
        policy_meta = _effective_policy_meta(
            effective_policy,
            deployment_max=self._settings.rag_generation_deployment_max_output_tokens,
        )
        policy_meta["projectId"] = project_id

        rollout = get_rollout_trace()

        plan_started = monotonic()
        plan = plan_query(message, max_chars=self._settings.rag_query_max_message_chars, knowledge_base_ids=knowledge_base_ids)
        await _notify_progress(on_progress, "planning", "Memahami pertanyaan dan menyiapkan pencarian...")

        rollout.record(
            "context_assembled",
            {
                "route": plan.route.value if hasattr(plan.route, "value") else str(plan.route),
                "standalone_query": getattr(plan, "standalone_query", "") or "",
            },
            turn_id=trace_id,
        )

        tracer = get_tracer()
        tracer.emit(
            "query.plan",
            route=plan.route.value if hasattr(plan.route, "value") else str(plan.route),
            standalone=getattr(plan, "standalone_query", "") or "",
            ms=_duration_ms(plan_started),
        )

        # Snapshot prior turns before persisting the current user message so the
        # current question is only sent as the final generation prompt.
        conversation_messages = await self._recent_messages(tenant=tenant, conversation_id=conversation_id)

        guardrail = evaluate_query(message, profile=effective_policy.guardrails)
        if not guardrail.allowed:
            await self._record_policy_decision(
                tenant=tenant,
                knowledge_base_id=knowledge_base_ids[0] if knowledge_base_ids else None,
                project_id=project_id,
                policy=effective_policy,
                stage="INPUT",
                decision="DENY",
                reason=guardrail.reason or "blocked",
                trace_id=trace_id,
            )
            rollout.record(
                "policy_decision",
                {"decision": "denied", "policy": "query_guardrail", "reason": guardrail.reason or "blocked"},
                turn_id=trace_id,
            )
            return await self._finish_refused(
                tenant=tenant,
                plan=plan,
                trace_id=trace_id,
                conversation_id=conversation_id,
                limitation=guardrail.reason or "This request cannot be answered due to safety guardrails.",
                decomposition={"triggered": False, "reason": "guardrail", "effectivePolicy": policy_meta},
                memory={"triggered": False, "chunks_retrieved": 0},
            )

        # Persist admitted user input only after input guardrails pass.
        # Snapshot (_recent_messages) completed above; base score is a pure sync
        # function so precomputing keeps planner identical when run in parallel.
        base_complexity = complexity_score(message)
        branch_sem = asyncio.Semaphore(4)

        async def _branch_save_turn() -> None:
            started = monotonic()
            try:
                async with branch_sem:
                    await asyncio.wait_for(
                        self._save_turn(
                            tenant=tenant,
                            conversation_id=conversation_id,
                            speaker="user",
                            content=message,
                        ),
                        timeout=5,
                    )
            except TimeoutError:
                logger.warning("query branch save_turn timeout trace_id=%s", trace_id)
            except Exception:
                logger.warning("query branch save_turn failed trace_id=%s", trace_id, exc_info=True)
            finally:
                tracer.emit("query.branch.save_turn", ms=_duration_ms(started))

        async def _branch_memory() -> dict[str, object]:
            started = monotonic()
            fallback: dict[str, object] = {"triggered": False, "chunks_retrieved": 0, "oldest_memory_age_days": None, "context_block": None}
            try:
                async with branch_sem:
                    result = await asyncio.wait_for(
                        self._retrieve_memory(
                            tenant=tenant,
                            message=message,
                            knowledge_base_ids=knowledge_base_ids,
                            project_id=project_id,
                            memory_enabled=memory_enabled,
                            session=session,
                        ),
                        timeout=4,
                    )
            except TimeoutError:
                logger.warning("query branch memory timeout trace_id=%s", trace_id)
                tracer.emit("query.branch.memory", ms=_duration_ms(started), triggered=False, reason="timeout")
                return {**fallback, "reason": "timeout"}
            except Exception:
                logger.warning("query branch memory failed trace_id=%s", trace_id, exc_info=True)
                tracer.emit("query.branch.memory", ms=_duration_ms(started), triggered=False, reason="error")
                return {**fallback, "reason": "error"}
            tracer.emit("query.branch.memory", ms=_duration_ms(started), triggered=bool(result.get("triggered")))
            return result

        async def _branch_decomposition() -> dict[str, object]:
            started = monotonic()
            try:
                async with branch_sem:
                    result = await asyncio.wait_for(
                        self._compute_decomposition_meta(
                            tenant=tenant,
                            message=message,
                            knowledge_base_ids=knowledge_base_ids,
                            project_id=project_id,
                            decomposition_enabled=decomposition_enabled,
                            decomposition_max_sub_queries=decomposition_max_sub_queries,
                        ),
                        timeout=8,
                    )
            except TimeoutError:
                logger.warning("query branch decomposition timeout trace_id=%s", trace_id)
                tracer.emit("query.branch.decomposition", ms=_duration_ms(started), triggered=False, reason="timeout")
                return {"triggered": False, "complexity_score": base_complexity, "reason": "timeout"}
            except Exception:
                logger.warning("query branch decomposition failed trace_id=%s", trace_id, exc_info=True)
                tracer.emit("query.branch.decomposition", ms=_duration_ms(started), triggered=False, reason="error")
                return {"triggered": False, "complexity_score": base_complexity, "reason": "error"}
            tracer.emit("query.branch.decomposition", ms=_duration_ms(started), triggered=bool(result.get("triggered")))
            return result

        async def _branch_planner() -> dict[str, object]:
            started = monotonic()
            try:
                async with branch_sem:
                    result = await asyncio.wait_for(
                        self._compute_planner_meta(
                            tenant=tenant,
                            message=message,
                            knowledge_base_ids=knowledge_base_ids,
                            project_id=project_id,
                            planner_enabled=planner_enabled,
                            planner_max_tasks=planner_max_tasks,
                            planner_task_types=planner_task_types,
                            precomputed_complexity_score=base_complexity,
                        ),
                        timeout=8,
                    )
            except TimeoutError:
                logger.warning("query branch planner timeout trace_id=%s", trace_id)
                tracer.emit("query.branch.planner", ms=_duration_ms(started), triggered=False, reason="timeout")
                return {"triggered": False, "reason": "timeout", "complexity_score": base_complexity}
            except Exception:
                logger.warning("query branch planner failed trace_id=%s", trace_id, exc_info=True)
                tracer.emit("query.branch.planner", ms=_duration_ms(started), triggered=False, reason="error")
                return {"triggered": False, "reason": "error", "complexity_score": base_complexity}
            tracer.emit("query.branch.planner", ms=_duration_ms(started), triggered=bool(result.get("triggered")))
            return result

        async def _branch_auth() -> tuple[str, ...]:
            started = monotonic()
            try:
                async with branch_sem:
                    result = await asyncio.wait_for(
                        self._authorized_knowledge_base_ids(tenant=tenant, knowledge_base_ids=knowledge_base_ids),
                        timeout=8,
                    )
            except TimeoutError:
                tracer.emit("query.branch.auth", ms=_duration_ms(started), error="timeout")
                logger.warning("query branch auth timeout trace_id=%s", trace_id)
                raise
            except Exception:
                tracer.emit("query.branch.auth", ms=_duration_ms(started), error="error")
                raise
            tracer.emit("query.branch.auth", ms=_duration_ms(started), count=len(result))
            return result

        _, memory_meta, decomposition_raw, planner_meta, authorized_ids = await asyncio.gather(
            _branch_save_turn(),
            _branch_memory(),
            _branch_decomposition(),
            _branch_planner(),
            _branch_auth(),
        )
        rollout.record(
            "user_message",
            {
                "conversation_id": conversation_id,
                "messageHash": _message_hash(message),
                "messageChars": len(message),
                "knowledge_base_ids": list(knowledge_base_ids),
            },
            turn_id=trace_id,
        )
        decomposition_meta = {**decomposition_raw, "effectivePolicy": policy_meta}
        if self._planner_configs is not None or planner_enabled is not None:
            decomposition_meta = {**decomposition_meta, "planner": planner_meta}

        if not self._settings.rag_query_enabled:
            return await self._finish_abstain(
                tenant=tenant,
                plan=plan,
                trace_id=trace_id,
                conversation_id=conversation_id,
                limitation="Query is not enabled for this deployment.",
                decomposition=decomposition_meta,
                memory=memory_meta,
            )

        if plan.route is QueryRoute.CLARIFY:
            return await self._finish_abstain(
                tenant=tenant,
                plan=plan,
                trace_id=trace_id,
                conversation_id=conversation_id,
                limitation=plan.reason or "Evidence is unavailable.",
                decomposition=decomposition_meta,
                memory=memory_meta,
            )

        authorized_ids = await self._authorized_knowledge_base_ids(tenant=tenant, knowledge_base_ids=knowledge_base_ids)
        generations = await self._generations.find_active_for_knowledge_bases(tenant_id=tenant.tenant_id, knowledge_base_ids=authorized_ids) if authorized_ids else []

        await _notify_progress(on_progress, "retrieving", "Mengambil referensi dari knowledge base...")

        return await self._run_answer(
            tenant=tenant,
            plan=plan,
            trace_id=trace_id,
            conversation_id=conversation_id,
            authorized_ids=authorized_ids,
            project_id=project_id,
            generations=generations,
            policy=effective_policy,
            decomposition_meta=decomposition_meta,
            memory_meta=memory_meta,
            conversation_messages=conversation_messages,
            session=session,
            on_progress=on_progress,
        )

    async def _run_answer(
        self,
        *,
        tenant: TenantContext,
        plan: QueryPlan,
        trace_id: str,
        conversation_id: str | None,
        authorized_ids: tuple[str, ...],
        project_id: str | None,
        generations: list[IndexGeneration],
        policy: EffectiveAnswerPolicy,
        decomposition_meta: dict[str, object],
        memory_meta: dict[str, object],
        conversation_messages: list[dict[str, str]] | None = None,
        planner_meta: dict[str, object] | None = None,
        session: AsyncSession | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, object]:
        """Run optional retrieval, then generate a grounded or general answer."""
        active_generation_ids = tuple(generation.id for generation in generations)
        collection = self._settings.rag_query_profile_id or "rag"
        retrieval = self._retrieval
        retrieval_available = bool(authorized_ids and generations and retrieval)

        # Resolve retrieval profile from active index profile
        embedding_profile_id: str | None = None
        sparse_profile_id: str | None = None
        index_profile_id: str | None = None
        if retrieval_available and self._index_profiles:
            index_profile = await self._index_profiles.find_active(tenant_id=tenant.tenant_id)
            if index_profile is not None:
                index_profile_id = index_profile.id
                embedding_profile_id = index_profile.embedding_profile_id
                sparse_profile_id = index_profile.sparse_profile_id
                collection = index_profile.collection or collection

        query_text = plan.standalone_query or plan.original_query
        questions = [query_text]
        raw_supplementary = (memory_meta or {}).get("context_block")
        supplementary = raw_supplementary if isinstance(raw_supplementary, str) else None
        merged: list[dict[str, object]] = []
        task_meta: list[dict[str, object]] = []
        resume_meta: dict[str, object] | None = None
        mcp_provenance: list[dict[str, object]] = []
        planner_value = decomposition_meta.get("planner")
        nested_planner_meta = planner_value if isinstance(planner_value, dict) else None
        if nested_planner_meta and nested_planner_meta.get("triggered") and retrieval_available and embedding_profile_id:
            planned = await self._execute_planned_tasks(
                tenant=tenant,
                query=query_text,
                knowledge_base_id=authorized_ids[0],
                project_id=project_id,
                authorized_ids=authorized_ids,
                active_generation_ids=active_generation_ids,
                collection=collection,
                embedding_profile_id=embedding_profile_id,
                sparse_profile_id=sparse_profile_id,
                index_profile_id=index_profile_id,
                planner_meta=nested_planner_meta,
                policy=policy,
                session=session,
            )
            if planned is not None:
                merged, task_meta, resume_meta, planner_supplementary, mcp_provenance = planned
                if planner_supplementary:
                    supplementary = "\n\n".join(part for part in (supplementary, planner_supplementary) if part)
                decomposition_meta = {**decomposition_meta, "tasks": task_meta, "resume": resume_meta}
                questions = []
        # If decomposition triggered, use sub-queries
        if questions and decomposition_meta.get("triggered") and self._decomposition_configs and authorized_ids:
            sub_queries = await self._decompose(
                tenant=tenant,
                message=query_text,
                knowledge_base_id=authorized_ids[0],
                project_id=project_id,
            )
            if sub_queries:
                questions = sub_queries

        # Parallel retrieval across sub-queries when the task planner is not active.
        dense_results: list[list[dict[str, object]]] = []
        sparse_results: list[list[dict[str, object]]] = []
        if retrieval is not None and retrieval_available and embedding_profile_id and questions:
            results = await asyncio.gather(
                *[
                    retrieval.retrieve(
                        tenant=tenant,
                        query=q,
                        collection=collection,
                        knowledge_base_ids=authorized_ids,
                        active_generation_ids=active_generation_ids,
                        embedding_profile_id=embedding_profile_id,
                        sparse_profile_id=sparse_profile_id,
                        index_profile_id=index_profile_id,
                    )
                    for q in questions
                ],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, BaseException):
                    logger.warning("Retrieval failed: %s", r)
                    continue
                dense, sparse = r
                dense_results.append(dense)
                sparse_results.append(sparse)

        if questions and (dense_results or sparse_results):
            merged, _ = merge_evidence([*dense_results, *sparse_results], top_k=self._settings.rag_context_max_chunks)

        # Build evidence context
        evidence_started = monotonic()
        evidence_chunks = _to_evidence_chunks(merged, tenant_id=tenant.tenant_id)
        context = build_evidence_context(
            chunks=evidence_chunks,
            tenant_id=tenant.tenant_id,
            active_generation_ids=active_generation_ids,
            token_budget=self._settings.rag_context_token_budget,
            output_reserve=policy.effective_output_budget(
                deployment_max=self._settings.rag_generation_deployment_max_output_tokens,
            ),
        )
        if policy.answer_behavior.allows_mcp and mcp_provenance:
            context = append_mcp_evidence(
                context,
                references=mcp_provenance,
                token_budget=self._settings.rag_context_token_budget,
                output_reserve=policy.effective_output_budget(
                    deployment_max=self._settings.rag_generation_deployment_max_output_tokens,
                ),
            )

        # Evidence quality determines provenance, not whether the LLM may answer.
        decision = gate_evidence(
            candidate_count=len(merged),
            independent_source_count=_independent_sources(merged),
            top_score=_top_score(merged),
            retry_attempted=False,
        )
        if policy.answer_behavior.allows_mcp and any(citation.source_kind.value == "MCP" for citation in context.citations):
            decision = EvidenceDecision(EvidenceLevel.MEDIUM, False, QueryRoute.GROUNDED)

        tracer = get_tracer()
        tracer.emit(
            "query.evidence",
            chunks=len(evidence_chunks),
            tokens=len(context.prompt_data or "") // 4,
            budget=self._settings.rag_context_token_budget,
            ms=_duration_ms(evidence_started),
            verbose_meta={"gated": decision.route is QueryRoute.GROUNDED},
        )

        if decision.route is not QueryRoute.GROUNDED:
            no_evidence_action = policy.answer_behavior.no_evidence_action
            requires_allowed_source = policy.answer_behavior.greeting_policy.value != "ALLOW_UNGROUNDED"
            if not policy.answer_behavior.allows_general_knowledge or no_evidence_action is not NoEvidenceAction.ANSWER_UNGROUNDED or requires_allowed_source:
                limitation = "The selected policy does not allow an answer without authorized evidence."
                if no_evidence_action is NoEvidenceAction.REFUSE or policy.answer_behavior.greeting_policy.value == "REFUSE":
                    return await self._finish_refused(
                        tenant=tenant,
                        plan=plan,
                        trace_id=trace_id,
                        conversation_id=conversation_id,
                        limitation=limitation,
                        decomposition=decomposition_meta,
                        memory=memory_meta,
                    )
                return await self._finish_abstain(
                    tenant=tenant,
                    plan=plan,
                    trace_id=trace_id,
                    conversation_id=conversation_id,
                    limitation=limitation,
                    decomposition=decomposition_meta,
                    memory=memory_meta,
                )

        # Generate
        await _notify_progress(on_progress, "generating", "Menyusun jawaban berdasarkan konteks yang ditemukan...")
        generation = self._generation
        if generation is None:
            return await self._finish_abstain(
                tenant=tenant,
                plan=plan,
                trace_id=trace_id,
                conversation_id=conversation_id,
                limitation="Generation is not configured.",
                decomposition=decomposition_meta,
                memory=memory_meta,
            )

        generation_profile_id = self._settings.rag_query_profile_id or "default-v1"
        answer = await generation.generate(
            tenant=tenant,
            question=query_text,
            evidence=context,
            profile_id=generation_profile_id,
            supplementary=supplementary,
            messages=conversation_messages or [],
            grounded=decision.route is QueryRoute.GROUNDED,
            policy=policy,
        )

        answer_text = _render_answer(answer)
        await _notify_progress(on_progress, "validating", "Memvalidasi jawaban, guardrail, dan sitasi...")
        answer_guardrail = evaluate_answer(answer_text, profile=policy.guardrails)
        if not answer_guardrail.allowed:
            await self._record_policy_decision(
                tenant=tenant,
                knowledge_base_id=authorized_ids[0] if authorized_ids else None,
                project_id=project_id,
                policy=policy,
                stage="OUTPUT",
                decision="DENY",
                reason=answer_guardrail.reason or "blocked",
                trace_id=trace_id,
            )
            return await self._finish_refused(
                tenant=tenant,
                plan=plan,
                trace_id=trace_id,
                conversation_id=conversation_id,
                limitation=answer_guardrail.reason or "The generated answer was blocked by safety guardrails.",
                decomposition=decomposition_meta,
                memory=memory_meta,
            )

        async def repair_answer(errors: tuple[str, ...]) -> GroundedAnswer:
            repair_context = (
                "A previous structured answer failed deterministic validation. Return one corrected structured answer. "
                "Use only citation IDs present in EVIDENCE, do not mention this repair, and do not add unsupported claims. "
                f"Validation errors: {', '.join(errors)}"
            )
            return await generation.generate(
                tenant=tenant,
                question=query_text,
                evidence=context,
                profile_id=generation_profile_id,
                supplementary=repair_context,
                messages=conversation_messages or [],
                grounded=True,
                policy=policy,
            )

        if decision.route is QueryRoute.GROUNDED:
            validated_answer, validation, repair_attempted = await self._answer_validation.validate_or_abstain(
                answer=answer,
                evidence=context,
                repair=repair_answer,
                tenant_id=tenant.tenant_id,
                trace_id=trace_id,
            )
        else:
            validated_answer = answer
            validation = AnswerValidation(is_valid=True, errors=())
            repair_attempted = False
        get_rollout_trace().record(
            "answer_validation",
            {
                "valid": validation.is_valid,
                "repair_attempted": repair_attempted,
                "error_count": len(validation.errors),
            },
            turn_id=trace_id,
        )
        grounded = decision.route is QueryRoute.GROUNDED and validation.is_valid
        if validated_answer is not None:
            answer = validated_answer
            answer_text = _render_answer(answer)
            final_answer_guardrail = evaluate_answer(answer_text, profile=policy.guardrails)
            if not final_answer_guardrail.allowed:
                await self._record_policy_decision(
                    tenant=tenant,
                    knowledge_base_id=authorized_ids[0] if authorized_ids else None,
                    project_id=project_id,
                    policy=policy,
                    stage="OUTPUT",
                    decision="DENY",
                    reason=final_answer_guardrail.reason or "blocked",
                    trace_id=trace_id,
                )
                return await self._finish_refused(
                    tenant=tenant,
                    plan=plan,
                    trace_id=trace_id,
                    conversation_id=conversation_id,
                    limitation=final_answer_guardrail.reason or "The generated answer was blocked by safety guardrails.",
                    decomposition=decomposition_meta,
                    memory=memory_meta,
                )
        if decision.route is QueryRoute.GROUNDED and not validation.is_valid:
            limitation = "This answer could not be fully grounded in the selected knowledge bases."
            if policy.answer_behavior.no_evidence_action is NoEvidenceAction.REFUSE:
                return await self._finish_refused(
                    tenant=tenant,
                    plan=plan,
                    trace_id=trace_id,
                    conversation_id=conversation_id,
                    limitation=limitation,
                    decomposition=decomposition_meta,
                    memory=memory_meta,
                )
            return await self._finish_abstain(
                tenant=tenant,
                plan=plan,
                trace_id=trace_id,
                conversation_id=conversation_id,
                limitation=limitation,
                decomposition=decomposition_meta,
                memory=memory_meta,
            )
        if not grounded:
            limitation = "This answer is not grounded in the selected knowledge bases."
            return await self._finish_answered(
                tenant=tenant,
                plan=plan,
                trace_id=trace_id,
                conversation_id=conversation_id,
                answer=answer_text,
                limitation=limitation,
                decomposition=decomposition_meta,
                memory=memory_meta,
            )

        return await self._finish_grounded(
            tenant=tenant,
            plan=plan,
            trace_id=trace_id,
            conversation_id=conversation_id,
            authorized_ids=authorized_ids,
            generations=generations,
            answer=answer,
            context=context,
            decision=decision,
            decomposition=decomposition_meta,
            memory=memory_meta,
            conversation_messages=conversation_messages,
        )

    async def _execute_planned_tasks(
        self,
        *,
        tenant: TenantContext,
        query: str,
        knowledge_base_id: str,
        authorized_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
        collection: str,
        embedding_profile_id: str,
        sparse_profile_id: str | None,
        index_profile_id: str | None,
        planner_meta: dict[str, object],
        policy: EffectiveAnswerPolicy,
        session: AsyncSession | None,
        project_id: str | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object], str, list[dict[str, object]]] | None:
        generation = self._generation
        retrieval = self._retrieval
        if self._planner_configs is None or generation is None or retrieval is None:
            return None
        from app.infrastructure.rag_catalog import SqlAlchemyModelProfileRepository

        config = None
        find_by_project = getattr(self._planner_configs, "find_by_project", None)
        if project_id is not None and find_by_project is not None:
            config = await find_by_project(tenant_id=tenant.tenant_id, project_id=project_id)
        if config is None:
            config = await self._planner_configs.find_by_knowledge_base(
                tenant_id=tenant.tenant_id,
                knowledge_base_id=knowledge_base_id,
            )
        if config is None:
            return None
        config = replace(config, max_tasks=_int_value(planner_meta.get("max_tasks"), config.max_tasks))
        owns_session = session is None
        active_session = session
        if active_session is None:
            # BUG-API-05: use the module-level singleton factory instead of
            # creating a new engine, and enter the session as a context manager
            # so it is properly closed (and rolled back on error) even if an
            # exception escapes the try/finally below.
            from app.infrastructure.database import _get_session_factory

            active_session = _get_session_factory()()
        try:
            profile = await SqlAlchemyModelProfileRepository(active_session).find_by_id(tenant_id=tenant.tenant_id, profile_id=config.model_profile_id)
            if profile is None:
                return None
            available_tools = ""
            mcp_allowed = bool(self._mcp_runtime and planner_meta.get("mcp_enabled") and policy.answer_behavior.allows_mcp)
            if mcp_allowed and self._mcp_runtime is not None:
                try:
                    allowed_tools = await self._mcp_runtime.list_allowed_tools(tenant=tenant)
                    available_tools = "\n".join(f"- id={tool.id} name={tool.name}: {tool.description}" for tool in allowed_tools)
                    get_rollout_trace().record(
                        "tool_catalog",
                        {
                            "knowledge_base_id": knowledge_base_id,
                            "tools": [
                                {
                                    "id": tool.id,
                                    "name": tool.name,
                                    "description": tool.description,
                                    "input_schema": tool.input_schema,
                                }
                                for tool in allowed_tools
                            ],
                        },
                    )
                except Exception:
                    pass

            task_plan = await QueryPlanner(self._settings).plan(
                query=query,
                config=config,
                knowledge_base_name=knowledge_base_id,
                model_profile=profile,
                available_tools=available_tools,
                allowed_types=_planner_allowed_types(planner_meta.get("task_types"), policy),
                session=active_session,
            )

            async def retrieve_task(task: TaskSpec) -> object:
                if task.query is None:
                    return []
                dense, sparse = await retrieval.retrieve(
                    tenant=tenant,
                    query=task.query,
                    collection=collection,
                    knowledge_base_ids=authorized_ids,
                    active_generation_ids=active_generation_ids,
                    embedding_profile_id=embedding_profile_id,
                    sparse_profile_id=sparse_profile_id,
                    index_profile_id=index_profile_id,
                )
                return merge_evidence([dense, sparse], top_k=self._settings.rag_context_max_chunks)[0]

            async def general_task(task: TaskSpec) -> object:
                if not policy.answer_behavior.allows_general_knowledge:
                    raise ValueError("general_task_not_allowed_by_source_policy")
                return await generation.generate_supplementary(
                    tenant=tenant,
                    question=task.query or query,
                    profile_id=config.model_profile_id,
                    policy=policy,
                )

            results = await TaskExecutor(
                rag_handler=retrieve_task,
                general_handler=general_task,
                mcp_enabled=mcp_allowed,
                mcp_handler=self._mcp_handler(tenant, policy=policy) if mcp_allowed else None,
                task_timeout_seconds=config.task_timeout_seconds,
                guardrails=policy.guardrails,
            ).execute(task_plan.tasks)
        finally:
            if owns_session and active_session is not None:
                await active_session.close()
        resumed = TaskResumer().resume(results, top_k=self._settings.rag_context_max_chunks)
        planner_meta["task_count"] = len(task_plan.tasks)
        planner_meta["planner_fallback"] = task_plan.fallback
        task_trace: list[dict[str, object]] = [
            {
                "id": result.task_id,
                "type": result.task_type.value,
                "status": result.status,
                "duration_ms": result.duration_ms,
                "reason": result.error,
                "evidence_count": len(result.rag or []),
                "depends_on": list(result.dependency_ids),
                "dependency_context_chars": result.dependency_context_chars,
            }
            for result in results
        ]
        resume_trace = {
            "merged_evidence_count": len(resumed.evidence),
            "dedup_removed": resumed.dedup_removed,
            "rerank_route": resumed.route,
            "supplementary_blocks": resumed.supplementary_blocks,
            "mcp_provenance_count": len(resumed.mcp_provenance),
        }
        return list(resumed.evidence), task_trace, resume_trace, resumed.supplementary_context, list(resumed.mcp_provenance)

    def _mcp_handler(self, tenant: TenantContext, *, policy: EffectiveAnswerPolicy) -> Callable[[TaskSpec], Awaitable[object]]:
        async def invoke(task: TaskSpec) -> object:
            if self._mcp_runtime is None or task.tool_ref is None:
                return {}
            return await self._mcp_runtime.invoke_tool(
                tenant=tenant,
                tool_id=task.tool_ref,
                arguments=task.arguments,
                max_payload_bytes=policy.guardrails.max_tool_payload_bytes,
                timeout_seconds=policy.guardrails.max_tool_timeout_seconds,
                freshness_seconds=policy.guardrails.max_mcp_freshness_seconds,
            )

        return invoke

    async def _decompose(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_id: str,
        project_id: str | None = None,
    ) -> list[str]:
        """Run the LLM decomposer for a configured KB. Returns [] on failure/fallback."""
        try:
            from app.application.query_decomposer import QueryDecomposer
            from app.infrastructure.database import get_session_factory
            from app.infrastructure.rag_catalog import SqlAlchemyModelProfileRepository

            if not self._decomposition_configs:
                return []
            config = None
            find_by_project = getattr(self._decomposition_configs, "find_by_project", None)
            if project_id is not None and find_by_project is not None:
                config = await find_by_project(tenant_id=tenant.tenant_id, project_id=project_id)
            if config is None:
                config = await self._decomposition_configs.find_by_knowledge_base(
                    tenant_id=tenant.tenant_id,
                    knowledge_base_id=knowledge_base_id,
                )
            if config is None or not config.enabled:
                return []

            session_factory = get_session_factory()
            async with session_factory() as session:
                profile_repo = SqlAlchemyModelProfileRepository(session)
                model_profile = await profile_repo.find_by_id(tenant_id=tenant.tenant_id, profile_id=config.model_profile_id)
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

    async def _finish_answered(
        self,
        *,
        tenant: TenantContext,
        plan: QueryPlan,
        trace_id: str,
        conversation_id: str | None,
        answer: str,
        limitation: str | None,
        decomposition: dict[str, object],
        memory: dict[str, object],
    ) -> dict[str, object]:
        return await self._record_and_return(
            tenant=tenant,
            plan=plan,
            trace_id=trace_id,
            conversation_id=conversation_id,
            route=QueryRoute.ANSWERED.value,
            evidence_level=EvidenceLevel.NONE.value,
            citations=(),
            answer=answer,
            limitation=limitation,
            decomposition=decomposition,
            memory=memory,
        )

    async def _finish_refused(
        self,
        *,
        tenant: TenantContext,
        plan: QueryPlan,
        trace_id: str,
        conversation_id: str | None,
        limitation: str,
        decomposition: dict[str, object],
        memory: dict[str, object],
    ) -> dict[str, object]:
        return await self._record_and_return(
            tenant=tenant,
            plan=plan,
            trace_id=trace_id,
            conversation_id=conversation_id,
            route=QueryRoute.REFUSED.value,
            evidence_level=EvidenceLevel.NONE.value,
            citations=(),
            answer=None,
            limitation=limitation,
            decomposition=decomposition,
            memory=memory,
        )

    async def _finish_abstain(
        self,
        *,
        tenant: TenantContext,
        plan: QueryPlan,
        trace_id: str,
        conversation_id: str | None,
        limitation: str,
        decomposition: dict[str, object],
        memory: dict[str, object],
        decision: EvidenceDecision | None = None,
    ) -> dict[str, object]:
        return await self._record_and_return(
            tenant=tenant,
            plan=plan,
            trace_id=trace_id,
            conversation_id=conversation_id,
            route=QueryRoute.ABSTAIN.value,
            evidence_level=EvidenceLevel.NONE.value,
            citations=(),
            answer=None,
            limitation=limitation,
            decomposition=decomposition,
            memory=memory,
        )

    async def _finish_grounded(
        self,
        *,
        tenant: TenantContext,
        plan: QueryPlan,
        trace_id: str,
        conversation_id: str | None,
        authorized_ids: tuple[str, ...],
        generations: list[IndexGeneration],
        answer: GroundedAnswer,
        context: EvidenceContext,
        decision: EvidenceDecision,
        decomposition: dict[str, object],
        memory: dict[str, object],
        conversation_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        citations = [_citation_dto(c) for c in context.citations]
        answer_text = _render_answer(answer)

        # Persist the answer run first so we have its ID for feature extraction
        run_result = await self._record_and_return(
            tenant=tenant,
            plan=plan,
            trace_id=trace_id,
            conversation_id=conversation_id,
            route=QueryRoute.GROUNDED.value,
            evidence_level=decision.level.value,
            citations=tuple(citations),
            answer=answer_text,
            limitation=None,
            decomposition=decomposition,
            memory=memory,
        )

        # Extract + persist feature vector (task 4.3): persistence is async trace,
        # scoring stays sync to preserve confidenceScore in the response.
        confidence_score: float | None = None
        confidence_config = None
        try:
            answer_run = await self._answer_runs.find_by_trace_id(tenant_id=tenant.tenant_id, trace_id=trace_id)
            if answer_run is not None:
                index_profile_id = None
                if self._index_profiles:
                    ip = await self._index_profiles.find_active(tenant_id=tenant.tenant_id)
                    if ip is not None:
                        index_profile_id = ip.id
                profile_id = index_profile_id or self._settings.rag_query_profile_id
                feature_vector = self._feature_extractor.extract(answer_run)

                async def _persist_vector() -> None:
                    try:
                        await self._answer_runs.set_feature_vector(
                            tenant_id=tenant.tenant_id,
                            answer_run_id=answer_run.id,
                            feature_vector=feature_vector,
                        )
                    except Exception:
                        logger.warning("trace async set_feature_vector failed trace_id=%s", trace_id, exc_info=True)

                asyncio.create_task(_persist_vector())
                # Score (task 5.4)
                if self._confidence_scorer is not None:
                    confidence_score = await self._confidence_scorer.score(
                        tenant_id=tenant.tenant_id,
                        profile_id=profile_id,
                        feature_vector=feature_vector,
                    )
                    if hasattr(self._confidence_scorer, "_configs"):
                        confidence_config = await self._confidence_scorer._configs.get_or_default(
                            tenant_id=tenant.tenant_id,
                            retrieval_profile_id=profile_id,
                        )
        except Exception:
            logger.warning("Confidence scoring skipped trace_id=%s", trace_id, exc_info=True)

        # Emit confidence fields in completed event (task 5.4)
        if confidence_score is not None and confidence_config is not None and confidence_config.emit_numeric_score:
            run_result = {
                **run_result,
                "confidenceScore": confidence_score,
                "abstentionThreshold": confidence_config.abstention_threshold,
                "calibrationModelId": confidence_config.active_model_id,
            }

        return run_result

    async def _record_policy_decision(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str | None,
        project_id: str | None,
        policy: EffectiveAnswerPolicy,
        stage: str,
        decision: str,
        reason: str,
        trace_id: str,
    ) -> None:
        if self._answer_policy is None:
            return

        async def _write() -> None:
            try:
                await self._answer_policy.record_decision(
                    tenant=tenant,
                    knowledge_base_id=knowledge_base_id,
                    project_id=project_id,
                    policy=policy,
                    stage=stage,
                    decision=decision,
                    reason=reason,
                    trace_id=trace_id,
                )
            except Exception:
                logger.warning("Failed to persist policy decision trace_id=%s", trace_id, exc_info=True)

        # Trace/audit write off the critical path: return without waiting for commit.
        asyncio.create_task(_write())

    async def _record_and_return(
        self,
        *,
        tenant: TenantContext,
        plan: QueryPlan,
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
        raw_policy_meta = decomposition.get("effectivePolicy")
        policy_meta: dict[str, object] = raw_policy_meta if isinstance(raw_policy_meta, dict) else {}
        public_decomposition = {key: value for key, value in decomposition.items() if key != "effectivePolicy"}
        assistant_content = answer if answer else (limitation or "")
        result = {
            "answer": answer,
            "route": route,
            "evidenceLevel": evidence_level,
            "citations": list(citations),
            "limitations": limitations,
            "traceId": trace_id,
            "conversationId": conversation_id,
            **policy_meta,
            "decomposition": public_decomposition,
            **({"planner": public_decomposition["planner"]} if "planner" in public_decomposition else {}),
            **({"tasks": public_decomposition["tasks"]} if "tasks" in public_decomposition else {}),
            **({"resume": public_decomposition["resume"]} if "resume" in public_decomposition else {}),
            "memory": {
                "triggered": (memory or {}).get("triggered", False),
                "chunks_retrieved": (memory or {}).get("chunks_retrieved", 0),
                "oldest_memory_age_days": (memory or {}).get("oldest_memory_age_days"),
            },
        }
        rollout = get_rollout_trace()
        event = "assistant_response" if answer else "safe_abstention"
        rollout.record(
            event,
            {
                "route": route,
                "answer": answer,
                "limitations": limitations,
                "citations": list(citations),
                "trace_id": trace_id,
            },
            turn_id=trace_id,
        )

        # Trace/audit persistence off the critical path: same content, async timing.
        # Response is built above and returned without waiting for DB commits.
        # User turn (_save_turn user) stays synchronous in _query_admitted; only
        # trace/audit/assistant-history writes are backgrounded here.
        trace_details = self._trace_details
        profile_snapshot: dict[str, object] = {
            "profileId": self._settings.rag_query_profile_id,
            "effectivePolicy": policy_meta,
            "mandatoryFilter": qdrant_policy_filter(
                tenant=tenant,
                knowledge_base_ids=(),
                active_generation_ids=(),
            ),
        }
        summary: dict[str, object] = {
            "route": route,
            "reason": limitation,
            "decomposition": public_decomposition,
            **({"planner": public_decomposition["planner"]} if "planner" in public_decomposition else {}),
            **({"tasks": public_decomposition["tasks"]} if "tasks" in public_decomposition else {}),
            **({"resume": public_decomposition["resume"]} if "resume" in public_decomposition else {}),
            "memory": {
                "triggered": (memory or {}).get("triggered", False),
                "chunks_retrieved": (memory or {}).get("chunks_retrieved", 0),
            },
        }
        original_query = getattr(plan, "original_query", "")
        standalone_query = getattr(plan, "standalone_query", "")

        async def _persist() -> None:
            answer_run_id: str | None = None
            try:
                answer_run = await self._answer_runs.create(
                    tenant_id=tenant.tenant_id,
                    trace_id=trace_id,
                    conversation_id=conversation_id,
                    original_query=original_query,
                    standalone_query=standalone_query,
                    route=route,
                    evidence_level=evidence_level,
                    profile_snapshot=profile_snapshot,
                    limitations=tuple(limitations),
                )
                answer_run_id = answer_run.id
            except Exception:
                logger.warning("trace async answer_run create failed trace_id=%s", trace_id, exc_info=True)
            if trace_details is not None and answer_run_id is not None:
                try:
                    await trace_details.create_retrieval_summary(
                        tenant_id=tenant.tenant_id,
                        answer_run_id=answer_run_id,
                        summary=summary,
                    )
                except Exception:
                    logger.warning("trace async retrieval_summary failed trace_id=%s", trace_id, exc_info=True)
                try:
                    await trace_details.create_validation_outcome(
                        tenant_id=tenant.tenant_id,
                        answer_run_id=answer_run_id,
                        is_valid=True,
                        checks={"release": route, "validationExecuted": False},
                        repair_attempted=False,
                    )
                except Exception:
                    logger.warning("trace async validation_outcome failed trace_id=%s", trace_id, exc_info=True)
            if conversation_id is not None:
                try:
                    await self._save_turn(
                        tenant=tenant,
                        conversation_id=conversation_id,
                        speaker="assistant",
                        content=assistant_content,
                    )
                except Exception:
                    logger.warning("trace async assistant save failed trace_id=%s", trace_id, exc_info=True)

        asyncio.create_task(_persist())
        # Yield once so fast (fake/in-memory) writes finish before return in tests,
        # while slow DB commits stay in background and do not block the response.
        await asyncio.sleep(0)
        return result

    async def _compute_decomposition_meta(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        project_id: str | None,
        decomposition_enabled: bool | None,
        decomposition_max_sub_queries: int | None,
    ) -> dict[str, object]:
        score = complexity_score(message)
        if decomposition_enabled is False:
            return {"triggered": False, "complexity_score": score, "reason": "disabled_by_request"}
        config = None
        if self._decomposition_configs and knowledge_base_ids:
            try:
                find_by_project = getattr(self._decomposition_configs, "find_by_project", None)
                config = await find_by_project(tenant_id=tenant.tenant_id, project_id=project_id) if project_id is not None and find_by_project is not None else None
                if config is None:
                    config = await self._decomposition_configs.find_by_knowledge_base(
                        tenant_id=tenant.tenant_id,
                        knowledge_base_id=knowledge_base_ids[0],
                    )
            except Exception:
                pass
        if config is None or not config.enabled:
            return {"triggered": False, "complexity_score": score, "reason": "not_configured" if config is None else "disabled_in_config"}
        if score < config.min_complexity_score:
            return {"triggered": False, "complexity_score": score, "reason": "score_below_threshold", "threshold": config.min_complexity_score}
        max_sub_queries = decomposition_max_sub_queries or config.max_sub_queries
        return {"triggered": True, "complexity_score": score, "config_id": config.id, "max_sub_queries": max_sub_queries}

    async def _compute_planner_meta(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        project_id: str | None,
        planner_enabled: bool | None,
        planner_max_tasks: int | None,
        planner_task_types: tuple[str, ...] | None,
        precomputed_complexity_score: float | None = None,
    ) -> dict[str, object]:
        if planner_enabled is False:
            return {"triggered": False, "reason": "disabled_by_request"}
        if self._planner_configs is None or not knowledge_base_ids:
            return {"triggered": False, "reason": "not_configured"}
        try:
            find_by_project = getattr(self._planner_configs, "find_by_project", None)
            config = await find_by_project(tenant_id=tenant.tenant_id, project_id=project_id) if project_id is not None and find_by_project is not None else None
            if config is None:
                config = await self._planner_configs.find_by_knowledge_base(
                    tenant_id=tenant.tenant_id,
                    knowledge_base_id=knowledge_base_ids[0],
                )
        except Exception:
            return {"triggered": False, "reason": "config_load_error"}
        if config is None or not config.enabled:
            return {"triggered": False, "reason": "not_configured" if config is None else "disabled_in_config"}
        threshold = config.guardrails.get("min_complexity_score", 0.6)
        if not isinstance(threshold, (float, int)):
            threshold = 0.6
        score = precomputed_complexity_score if precomputed_complexity_score is not None else complexity_score(message)
        if score < threshold:
            return {"triggered": False, "complexity_score": score, "reason": "score_below_threshold", "threshold": threshold}
        raw_dependency_depth = config.guardrails.get("max_dependency_depth", 2)
        max_dependency_depth = max(1, min(2, _int_value(raw_dependency_depth, 2)))
        return {
            "triggered": True,
            "config_id": config.id,
            "complexity_score": score,
            "max_tasks": planner_max_tasks or config.max_tasks,
            "max_dependency_depth": max_dependency_depth,
            "task_types": list(planner_task_types or config.task_types),
            "mcp_enabled": config.mcp_enabled,
            "planner_fallback": False,
        }

    async def _save_turn(
        self,
        *,
        tenant: TenantContext,
        conversation_id: str,
        speaker: str,
        content: str,
    ) -> None:
        """Persist a message to conversation history. Silent on failure."""
        try:
            from datetime import datetime

            from app.domain.rag.conversation import ConversationMessage, ConversationSpeaker

            await self._conversations.ensure_conversation(
                tenant_id=tenant.tenant_id,
                user_id=tenant.user_id,
                conversation_id=conversation_id,
            )
            message = ConversationMessage(
                id=str(uuid4()),
                tenant_id=tenant.tenant_id,
                conversation_id=conversation_id,
                speaker=ConversationSpeaker.USER if speaker == "user" else ConversationSpeaker.ASSISTANT,
                content=content,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            await self._conversations.save_message(message=message)
        except Exception:
            logger.warning("Failed to save conversation message", exc_info=True)

    async def _recent_messages(self, *, tenant: TenantContext, conversation_id: str | None) -> list[dict[str, str]]:
        if conversation_id is None:
            return []
        messages = await self._conversations.recent_messages(
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            conversation_id=conversation_id,
            limit=self._settings.rag_query_recent_messages,
        )
        return [{"role": "user" if message.speaker.value == "USER" else "assistant", "content": message.content} for message in messages]

    async def _authorized_knowledge_base_ids(self, *, tenant: TenantContext, knowledge_base_ids: tuple[str, ...]) -> tuple[str, ...]:
        # Bounded parallel auth check: latency ~= slowest lookup, not sum.
        # Security preserved: only ACTIVE KBs pass; empty stays empty.
        if not knowledge_base_ids:
            return ()
        semaphore = asyncio.Semaphore(6)

        async def _check(kb_id: str) -> str | None:
            async with semaphore:
                knowledge_base = await self._knowledge_bases.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=kb_id)
                if knowledge_base is not None and knowledge_base.status is KnowledgeBaseStatus.ACTIVE:
                    return kb_id
                return None

        results = await asyncio.gather(*(_check(kb_id) for kb_id in knowledge_base_ids))
        return tuple(kb_id for kb_id in results if kb_id is not None)

    async def _retrieve_memory(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        project_id: str | None,
        memory_enabled: bool | None,
        session: AsyncSession | None,
    ) -> dict[str, object]:
        empty: dict[str, object] = {"triggered": False, "chunks_retrieved": 0, "oldest_memory_age_days": None, "context_block": None}
        # BUG-API-13: session is always provided by the FastAPI dependency in
        # normal flow so the `session is None` guard here is misleading. Keep
        # the guard for safety but make the condition explicit.
        if memory_enabled is False or not knowledge_base_ids:
            return empty
        if session is None:
            return empty
        try:
            from app.application.memory_retriever import MemoryRetriever

            retriever = MemoryRetriever(self._settings)
            return await retriever.retrieve(
                query=message,
                tenant_id=tenant.tenant_id,
                knowledge_base_id=knowledge_base_ids[0],
                project_id=project_id,
                user_id=tenant.user_id,
                session=session,
            )
        except Exception as e:
            logger.warning("Memory retrieval skipped: %s", e)
            return empty

    async def _enqueue_memory_summarization(
        self,
        *,
        tenant: TenantContext,
        conversation_id: str | None,
        knowledge_base_ids: tuple[str, ...],
        project_id: str | None = None,
        memory_enabled: bool | None,
        session: AsyncSession | None,
    ) -> None:
        """Schedule memory summarization without affecting the query result."""
        if memory_enabled is False or conversation_id is None or not knowledge_base_ids or session is None:
            return

        try:
            from app.infrastructure.rag_catalog import SqlAlchemyMemoryConfigRepository
            from app.workers.ingestion_worker import enqueue_memory_summarize

            config_repo = SqlAlchemyMemoryConfigRepository(session)
        except Exception:
            logger.warning("Memory summarization scheduling setup failed", exc_info=True)
            return

        project_config = await config_repo.find_by_project(tenant_id=tenant.tenant_id, project_id=project_id) if project_id is not None else None
        for knowledge_base_id in knowledge_base_ids:
            try:
                config = project_config or await config_repo.find_by_knowledge_base(
                    tenant_id=tenant.tenant_id,
                    knowledge_base_id=knowledge_base_id,
                )
                if config is None or not config.enabled:
                    continue

                await enqueue_memory_summarize(
                    conversation_id=conversation_id,
                    tenant_id=tenant.tenant_id,
                    knowledge_base_id=knowledge_base_id,
                    user_id=tenant.user_id,
                    project_id=project_id,
                    redis_url=self._settings.redis_url,
                    job_id=f"mem:{conversation_id}:{knowledge_base_id}:{uuid4()}",
                )
            except Exception:
                logger.warning(
                    "Memory summarization enqueue failed for conversation=%s knowledge_base=%s",
                    conversation_id,
                    knowledge_base_id,
                    exc_info=True,
                )


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
    versions: set[str] = set()
    for point in points:
        payload = point.get("payload")
        if isinstance(payload, dict):
            versions.add(str(payload.get("document_version_id") or ""))
    return len([v for v in versions if v])


def _top_score(points: list[dict[str, object]]) -> float | None:
    scores = [_float_value(point.get("score")) for point in points]
    return max(scores) if scores else None


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _int_value(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return default


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, (list, tuple, set)) else []


def _planner_allowed_types(value: object, policy: EffectiveAnswerPolicy) -> set[TaskType | str]:
    """Apply server-side source policy to planner task capabilities."""
    allowed: set[TaskType | str] = {TaskType.RAG}
    if policy.answer_behavior.allows_general_knowledge:
        allowed.add(TaskType.GENERAL)
    if policy.answer_behavior.allows_mcp:
        allowed.add(TaskType.MCP)
    valid_values = {task_type.value for task_type in TaskType}
    requested = {TaskType(item.upper()) for item in _string_list(value) if item.upper() in valid_values}
    return cast(set[TaskType | str], requested.intersection(allowed)) if requested else allowed


def _citation_dto(citation: object) -> dict[str, object]:
    source_kind = getattr(citation, "source_kind", None)
    produced_at = getattr(citation, "produced_at", None)
    expires_at = getattr(citation, "expires_at", None)
    return {
        "citationId": getattr(citation, "citation_id", ""),
        "chunkId": getattr(citation, "chunk_id", ""),
        "documentVersionId": getattr(citation, "document_version_id", ""),
        "title": getattr(citation, "title", ""),
        "locator": getattr(citation, "locator", None),
        "snippet": getattr(citation, "snippet", ""),
        "sourceKind": getattr(source_kind, "value", source_kind or "DOCUMENT"),
        "sourceId": getattr(citation, "source_id", None),
        "serverId": getattr(citation, "server_id", None),
        "toolId": getattr(citation, "tool_id", None),
        "invocationId": getattr(citation, "invocation_id", None),
        "traceId": getattr(citation, "trace_id", None),
        "producedAt": produced_at.isoformat() if produced_at else None,
        "expiresAt": expires_at.isoformat() if expires_at else None,
    }


def _effective_policy_meta(policy: EffectiveAnswerPolicy, *, deployment_max: int) -> dict[str, object]:
    source_kinds = ["DOCUMENT"]
    if policy.answer_behavior.allows_mcp:
        source_kinds.append("MCP")
    if policy.answer_behavior.allows_general_knowledge:
        source_kinds.append("GENERAL")
    return {
        "answerBehaviorVersion": policy.answer_behavior_version,
        "guardrailVersion": policy.guardrail_version,
        "sourcePolicy": policy.source_policy.value,
        "maxOutputTokens": policy.answer_behavior.max_output_tokens,
        "effectiveOutputTokens": policy.effective_output_budget(deployment_max=deployment_max),
        "sourceKinds": source_kinds,
        "responseStyle": policy.answer_behavior.response_style.value,
        "greetingPolicy": policy.answer_behavior.greeting_policy.value,
        "noEvidenceAction": policy.answer_behavior.no_evidence_action.value,
        "requireCitations": policy.answer_behavior.require_citations,
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
        parts.append("\n\nLimitations:\n" + "\n".join(f"- {limitation}" for limitation in answer.limitations))
    return "\n".join(parts) if parts else "No answer could be generated."


def _duration_ms(started_at: float) -> int:
    return int((monotonic() - started_at) * 1_000)


def _message_hash(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


async def _notify_progress(callback: ProgressCallback | None, stage: str, message: str) -> None:
    if callback is not None:
        await callback(stage, message)


def _record_safe_pipeline_metrics(*, tenant_id: str, trace_id: str, route: str, duration_ms: int) -> None:
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="planning", outcome=route, duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="retrieval", outcome="skipped", duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="reranking", outcome="skipped", duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="generation", outcome="skipped", duration_ms=duration_ms)
    record_query_metric(tenant_id=tenant_id, trace_id=trace_id, stage="validation", outcome="safe_abstention", duration_ms=duration_ms)
