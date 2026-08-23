"""LLM-based typed query planner."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.application.query_decomposer import _call_ollama, _call_openai, _render, validate_template
from app.core.dev_trace import get_tracer
from app.domain.rag.task_plan import TaskPlan, TaskType, fallback_task_plan, parse_task_plan

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.settings import Settings
    from app.domain.rag.catalog import DecompositionConfig
    from app.infrastructure.rag_catalog import ModelProfileRecord

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a query task planner. Return ONLY a JSON array of typed tasks. "
    "Supported types are RAG, MCP, and GENERAL. Maximum {{ max_tasks }} tasks."
)
DEFAULT_USER_PROMPT_TEMPLATE = (
    "Query: {{ query }}\nKnowledge base: {{ knowledge_base_name }}\n"
    "Available tools: {{ available_tools }}\nTasks (max {{ max_tasks }}):"
)


class QueryPlanner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def plan(
        self,
        *,
        query: str,
        config: DecompositionConfig,
        knowledge_base_name: str,
        model_profile: ModelProfileRecord,
        available_tools: str = "",
        allowed_types: set[TaskType | str] | None = None,
        session: AsyncSession | None = None,
    ) -> TaskPlan:
        context = {
            "query": query,
            "max_tasks": getattr(config, "max_tasks", getattr(config, "max_sub_queries", 4)),
            "available_tools": available_tools,
            "knowledge_base_name": knowledge_base_name,
        }
        try:
            validate_template(config.system_prompt)
            validate_template(config.user_prompt_template)
            system_prompt = _render(config.system_prompt, context)
            user_prompt = _render(config.user_prompt_template, context)
            raw = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_profile=model_profile,
                tenant_id=config.tenant_id,
                session=session,
                timeout=float(getattr(config, "task_timeout_seconds", 10)),
            )
            task_plan = parse_task_plan(raw, context["max_tasks"], allowed_types)
            tracer = get_tracer()
            async with tracer.op(
                "query.plan_tasks",
                count=len(task_plan.tasks),
                types=list({t.type.value if hasattr(t.type, "value") else str(t.type) for t in task_plan.tasks}),
                fallback=task_plan.fallback,
                system_tail=tracer._tail(system_prompt) if tracer.enabled else "",
                user_tail=tracer._tail(user_prompt) if tracer.enabled else "",
                verbose_meta={"tasks": [{"type": t.type.value if hasattr(t.type, "value") else str(t.type), "query": t.query, "tool_ref": t.tool_ref} for t in task_plan.tasks]},
            ):
                pass
            return task_plan
        except asyncio.TimeoutError:
            return fallback_task_plan(query, "timeout", allowed_types)
        except Exception as exc:
            logger.warning("LLM task planning failed: %s", exc)
            return fallback_task_plan(query, f"planner_error: {type(exc).__name__}", allowed_types)

    async def _call_llm(self, *, system_prompt: str, user_prompt: str, model_profile: ModelProfileRecord, tenant_id: str, session: AsyncSession | None, timeout: float = 10.0) -> str:
        from app.infrastructure.providers.registry import get_provider_api_key

        if model_profile.provider == "openai":
            api_key = await get_provider_api_key(provider="openai", key_name="api_key", tenant_id=tenant_id, session=session, settings=self._settings)
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            return await _call_openai(system_prompt, user_prompt, model_profile.model, api_key, timeout=timeout)
        if model_profile.provider == "ollama":
            base_url = await get_provider_api_key(provider="ollama", key_name="base_url", tenant_id=tenant_id, session=session, settings=self._settings) or getattr(self._settings, "ollama_base_url", "http://localhost:11434")
            return await _call_ollama(system_prompt, user_prompt, model_profile.model, base_url, timeout=timeout)
        raise ValueError(f"Unsupported LLM provider for planning: {model_profile.provider}")
