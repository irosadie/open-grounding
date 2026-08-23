"""Application service for per-knowledge-base planner configuration."""

from __future__ import annotations

from jinja2 import TemplateSyntaxError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.query_decomposer import validate_template
from app.application.query_planner import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT_TEMPLATE
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.rag.catalog import PlannerConfig
from app.domain.rag.task_plan import TaskType
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import SqlAlchemyKnowledgeBaseRepository, SqlAlchemyModelProfileRepository, SqlAlchemyPlannerConfigRepository

_GENERATION_KINDS = {"GENERATION", "CHAT", "generation", "chat"}


class PlannerConfigService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._repo = SqlAlchemyPlannerConfigRepository(session)
        self._model_repo = SqlAlchemyModelProfileRepository(session)
        self._kb_repo = SqlAlchemyKnowledgeBaseRepository(session)

    async def get(self, *, tenant: TenantContext, knowledge_base_id: str) -> PlannerConfig | None:
        return await self._repo.find_by_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)

    async def upsert(self, *, tenant: TenantContext, knowledge_base_id: str, enabled: bool, model_profile_id: str, system_prompt: str, user_prompt_template: str, max_tasks: int, task_timeout_seconds: int, task_types: list[str], mcp_enabled: bool, guardrails: dict[str, object]) -> PlannerConfig:
        if await self._kb_repo.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id) is None:
            raise DomainError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base not found", 404)
        profile = await self._model_repo.find_by_id(tenant_id=tenant.tenant_id, profile_id=model_profile_id)
        if profile is None:
            raise DomainError("MODEL_PROFILE_NOT_FOUND", "Model profile not found", 404)
        if profile.profile_kind not in _GENERATION_KINDS:
            raise DomainError("INVALID_MODEL_PROFILE_KIND", "Model profile must be a generation model", 422)
        for label, template in (("system_prompt", system_prompt), ("user_prompt_template", user_prompt_template)):
            try:
                validate_template(template)
            except TemplateSyntaxError as exc:
                raise DomainError("INVALID_PROMPT_TEMPLATE", f"Invalid Jinja2 template in {label}: {exc}", 422) from exc
        if not 1 <= max_tasks <= 8:
            raise DomainError("VALIDATION_ERROR", "max_tasks must be between 1 and 8", 422)
        if not 1 <= task_timeout_seconds <= 60:
            raise DomainError("VALIDATION_ERROR", "task_timeout_seconds must be between 1 and 60", 422)
        try:
            normalized_types = tuple(TaskType(value).value for value in task_types)
        except ValueError as exc:
            raise DomainError("VALIDATION_ERROR", "task_types must contain only RAG, MCP, or GENERAL", 422) from exc
        if not normalized_types:
            raise DomainError("VALIDATION_ERROR", "task_types must not be empty", 422)
        return await self._repo.upsert(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id, enabled=enabled, model_profile_id=model_profile_id, system_prompt=system_prompt, user_prompt_template=user_prompt_template, max_tasks=max_tasks, task_timeout_seconds=task_timeout_seconds, task_types=normalized_types, mcp_enabled=mcp_enabled, guardrails=guardrails)

    async def delete(self, *, tenant: TenantContext, knowledge_base_id: str) -> bool:
        return await self._repo.delete(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)

    def get_defaults(self) -> dict[str, object]:
        return {"systemPrompt": DEFAULT_SYSTEM_PROMPT, "userPromptTemplate": DEFAULT_USER_PROMPT_TEMPLATE, "maxTasks": 4, "taskTimeoutSeconds": 15, "taskTypes": [task_type.value for task_type in TaskType], "mcpEnabled": False, "guardrails": {}}
