"""LLM-based typed query planner."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.application.query_decomposer import _call_ollama, _call_openai, _render, validate_template
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
            raw = await self._call_llm(
                system_prompt=_render(config.system_prompt, context),
                user_prompt=_render(config.user_prompt_template, context),
                model_profile=model_profile,
                tenant_id=config.tenant_id,
                session=session,
            )
            return parse_task_plan(raw, context["max_tasks"], allowed_types)
        except asyncio.TimeoutError:
            return fallback_task_plan(query, "timeout")
        except Exception as exc:
            logger.warning("LLM task planning failed: %s", exc)
            return fallback_task_plan(query, f"planner_error: {type(exc).__name__}")

    async def _call_llm(self, *, system_prompt: str, user_prompt: str, model_profile: ModelProfileRecord, tenant_id: str, session: AsyncSession | None) -> str:
        from app.infrastructure.providers.registry import get_provider_api_key

        if model_profile.provider == "openai":
            api_key = await get_provider_api_key(provider="openai", key_name="api_key", tenant_id=tenant_id, session=session, settings=self._settings)
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            return await _call_openai(system_prompt, user_prompt, model_profile.model, api_key)
        if model_profile.provider == "ollama":
            base_url = await get_provider_api_key(provider="ollama", key_name="base_url", tenant_id=tenant_id, session=session, settings=self._settings) or getattr(self._settings, "ollama_base_url", "http://localhost:11434")
            return await _call_ollama(system_prompt, user_prompt, model_profile.model, base_url)
        raise ValueError(f"Unsupported LLM provider for planning: {model_profile.provider}")
