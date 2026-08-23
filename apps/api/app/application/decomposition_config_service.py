"""Application service for DecompositionConfig CRUD.

Validates model profile kind and Jinja2 templates before persisting.
"""

from __future__ import annotations

import logging

from jinja2 import TemplateSyntaxError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.query_decomposer import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
    validate_template,
)
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.rag.catalog import DecompositionConfig
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import (
    SqlAlchemyDecompositionConfigRepository,
    SqlAlchemyKnowledgeBaseRepository,
    SqlAlchemyModelProfileRepository,
)

logger = logging.getLogger(__name__)

# Generation model kinds — only these may be used as decomposition LLM
_GENERATION_KINDS = {"GENERATION", "CHAT", "generation", "chat"}


class DecompositionConfigService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = SqlAlchemyDecompositionConfigRepository(session)
        self._model_repo = SqlAlchemyModelProfileRepository(session)
        self._kb_repo = SqlAlchemyKnowledgeBaseRepository(session)

    async def get(self, *, tenant: TenantContext, knowledge_base_id: str) -> DecompositionConfig | None:
        return await self._repo.find_by_knowledge_base(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
        )

    async def upsert(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str,
        enabled: bool,
        model_profile_id: str,
        system_prompt: str,
        user_prompt_template: str,
        max_sub_queries: int,
        max_depth: int,
        min_complexity_score: float,
        guardrails: dict[str, object],
    ) -> DecompositionConfig:
        # Validate KB exists
        kb = await self._kb_repo.find_by_id(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
        )
        if kb is None:
            raise DomainError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base not found", 404)

        # Validate model profile kind
        profile = await self._model_repo.find_by_id(
            tenant_id=tenant.tenant_id,
            profile_id=model_profile_id,
        )
        if profile is None:
            raise DomainError("MODEL_PROFILE_NOT_FOUND", "Model profile not found", 404)
        if profile.profile_kind not in _GENERATION_KINDS:
            raise DomainError(
                "INVALID_MODEL_PROFILE_KIND",
                f"Model profile must be a generation model, got '{profile.profile_kind}'",
                422,
            )

        # Validate Jinja2 templates
        for label, tmpl in [("system_prompt", system_prompt), ("user_prompt_template", user_prompt_template)]:
            try:
                validate_template(tmpl)
            except TemplateSyntaxError as e:
                raise DomainError(
                    "INVALID_PROMPT_TEMPLATE",
                    f"Invalid Jinja2 template in {label}: {e}",
                    422,
                ) from e

        # Validate numeric bounds
        if not (1 <= max_sub_queries <= 5):
            raise DomainError("VALIDATION_ERROR", "max_sub_queries must be between 1 and 5", 422)
        if not (1 <= max_depth <= 3):
            raise DomainError("VALIDATION_ERROR", "max_depth must be between 1 and 3", 422)
        if not (0.0 <= min_complexity_score <= 1.0):
            raise DomainError("VALIDATION_ERROR", "min_complexity_score must be between 0.0 and 1.0", 422)

        return await self._repo.upsert(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            enabled=enabled,
            model_profile_id=model_profile_id,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            max_sub_queries=max_sub_queries,
            max_depth=max_depth,
            min_complexity_score=min_complexity_score,
            guardrails=guardrails,
        )

    async def delete(self, *, tenant: TenantContext, knowledge_base_id: str) -> bool:
        return await self._repo.delete(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
        )

    def get_defaults(self) -> dict[str, object]:
        return {
            "systemPrompt": DEFAULT_SYSTEM_PROMPT,
            "userPromptTemplate": DEFAULT_USER_PROMPT_TEMPLATE,
            "maxSubQueries": 3,
            "maxDepth": 2,
            "minComplexityScore": 0.6,
            "guardrails": {},
        }
