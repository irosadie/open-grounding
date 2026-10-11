"""LLM-based typed query planner."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.query_decomposer import _call_ollama, _call_openai, _render, validate_template
from app.core.dev_trace import _tail, get_tracer
from app.core.llm_rollout_trace import get_rollout_trace
from app.domain.rag.task_plan import TaskPlan, TaskType, fallback_task_plan, parse_task_plan

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.settings import Settings
    from app.domain.rag.catalog import DecompositionConfig, PlannerConfig
    from app.domain.rag.profiles import ModelProfile

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a query task planner. Return ONLY a JSON array of typed tasks. "
    "Supported types are RAG, MCP, and GENERAL. Maximum {{ max_tasks }} tasks. "
    "RAG and GENERAL tasks may use depends_on to reference earlier tasks; MCP tasks "
    "must not declare dependencies. Dependencies must be acyclic and at most {{ max_depth }} levels deep."
)
DEFAULT_USER_PROMPT_TEMPLATE = "Query: {{ query }}\nKnowledge base: {{ knowledge_base_name }}\nAvailable tools: {{ available_tools }}\nTasks (max {{ max_tasks }}, dependency depth {{ max_depth }}):"


def _max_dependency_depth(config: object) -> int:
    guardrails = getattr(config, "guardrails", {})
    raw_depth = guardrails.get("max_dependency_depth", 2) if isinstance(guardrails, dict) else 2
    try:
        return max(1, min(2, int(raw_depth)))
    except (TypeError, ValueError):
        return 2


class QueryPlanner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def plan(
        self,
        *,
        query: str,
        config: DecompositionConfig | PlannerConfig,
        knowledge_base_name: str,
        model_profile: ModelProfile,
        available_tools: str = "",
        allowed_types: set[TaskType | str] | None = None,
        session: AsyncSession | None = None,
    ) -> TaskPlan:
        context = {
            "query": query,
            "max_tasks": getattr(config, "max_tasks", getattr(config, "max_sub_queries", 4)),
            "max_depth": _max_dependency_depth(config),
            "available_tools": available_tools,
            "knowledge_base_name": knowledge_base_name,
        }
        raw: str | None = None
        trace = get_rollout_trace()
        try:
            validate_template(config.system_prompt)
            validate_template(config.user_prompt_template)
            system_prompt = _render(config.system_prompt, context)
            user_prompt = _render(config.user_prompt_template, context)
            tracer = get_tracer()
            verbose_meta: dict[str, object] = {}
            async with tracer.op(
                "query.plan_tasks",
                count=0,
                types=[],
                fallback=False,
                system_tail=_tail(system_prompt) if tracer.enabled else "",
                user_tail=_tail(user_prompt) if tracer.enabled else "",
                verbose_meta=verbose_meta,
            ) as trace_meta:
                raw = await self._call_llm(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model_profile=model_profile,
                    tenant_id=config.tenant_id,
                    session=session,
                    timeout=float(getattr(config, "task_timeout_seconds", 10)),
                )
                task_plan = parse_task_plan(raw, int(context["max_tasks"]), allowed_types, max_depth=int(context["max_depth"]))
                task_types = list({t.type.value if hasattr(t.type, "value") else str(t.type) for t in task_plan.tasks})
                trace_meta.update(count=len(task_plan.tasks), types=task_types, fallback=task_plan.fallback)
                verbose_meta["tasks"] = [
                    {
                        "type": t.type.value if hasattr(t.type, "value") else str(t.type),
                        "query": t.query,
                        "tool_ref": t.tool_ref,
                        "depends_on": list(t.depends_on),
                    }
                    for t in task_plan.tasks
                ]
                return task_plan
        except TimeoutError:
            trace.record("llm_error", {"operation": "query.plan_tasks", "error": "timeout"})
            trace.record("llm_fallback", {"operation": "query.plan_tasks", "reason": "timeout", "query": query})
            return fallback_task_plan(query, "timeout", allowed_types)
        except Exception as exc:
            logger.warning("LLM task planning failed: %s", exc)
            if raw is not None:
                trace.record(
                    "llm_parse_error",
                    {"operation": "query.plan_tasks", "raw_response": raw, "error_type": type(exc).__name__, "error": str(exc)},
                )
            trace.record("llm_fallback", {"operation": "query.plan_tasks", "reason": f"planner_error: {type(exc).__name__}", "query": query})
            return fallback_task_plan(query, f"planner_error: {type(exc).__name__}", allowed_types)

    async def _call_llm(self, *, system_prompt: str, user_prompt: str, model_profile: ModelProfile, tenant_id: str, session: AsyncSession | None, timeout: float = 10.0) -> str:
        from app.infrastructure.providers.registry import get_provider_api_key

        if model_profile.provider == "openai":
            api_key = await get_provider_api_key(provider="openai", key_name="api_key", tenant_id=tenant_id, session=session, settings=self._settings)
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            return await _call_openai(system_prompt, user_prompt, model_profile.model, api_key, timeout=timeout, operation="query.plan_tasks")
        if model_profile.provider == "ollama":
            base_url = await get_provider_api_key(provider="ollama", key_name="base_url", tenant_id=tenant_id, session=session, settings=self._settings) or str(
                getattr(self._settings, "ollama_base_url", "http://localhost:11434")
            )
            return await _call_ollama(system_prompt, user_prompt, model_profile.model, base_url, timeout=timeout, operation="query.plan_tasks")
        raise ValueError(f"Unsupported LLM provider for planning: {model_profile.provider}")
