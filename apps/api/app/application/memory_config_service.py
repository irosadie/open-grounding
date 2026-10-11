"""Memory configuration service — create/get/delete with validation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.memory_summarizer import MemorySummarizer, validate_jinja2_template
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import UserRole
from app.domain.rag.memory import DEFAULT_SYSTEM_PROMPT, MemoryConfig
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_projects import SqlAlchemyProjectRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_GENERATION_KINDS = {"GENERATION", "CHAT"}
_EMBEDDING_KINDS = {"EMBEDDING", "DENSE_EMBEDDING"}


class MemoryConfigService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._project_repo = SqlAlchemyProjectRepository(session)

    async def get(self, *, tenant: TenantContext, knowledge_base_id: str) -> MemoryConfig:
        from app.infrastructure.rag_catalog import SqlAlchemyMemoryConfigRepository

        repo = SqlAlchemyMemoryConfigRepository(self._session)
        config = await repo.find_by_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if config is None:
            raise DomainError.not_found("Memory config not found for this knowledge base")
        return config

    async def upsert(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str,
        enabled: bool,
        summarization_model_profile_id: str,
        embedding_profile_id: str,
        retention_days: int,
        retrieval_top_k: int,
        min_turns_to_summarize: int,
        system_prompt: str,
    ) -> MemoryConfig:
        self._require_legacy_kb_writes_enabled()
        from app.infrastructure.rag_catalog import (
            SqlAlchemyMemoryConfigRepository,
            SqlAlchemyModelProfileRepository,
        )

        # Validate retention_days, retrieval_top_k, min_turns_to_summarize ranges
        if not (1 <= retention_days <= 365):
            raise DomainError.validation("retention_days must be between 1 and 365")
        if not (1 <= retrieval_top_k <= 20):
            raise DomainError.validation("retrieval_top_k must be between 1 and 20")
        if not (1 <= min_turns_to_summarize <= 20):
            raise DomainError.validation("min_turns_to_summarize must be between 1 and 20")

        # Validate Jinja2 template
        if not validate_jinja2_template(system_prompt):
            raise DomainError("INVALID_PROMPT_TEMPLATE", "system_prompt is not a valid Jinja2 template", 422)

        profile_repo = SqlAlchemyModelProfileRepository(self._session)

        # Validate summarization model kind
        summ_profile = await profile_repo.find_by_id(tenant_id=tenant.tenant_id, profile_id=summarization_model_profile_id)
        if summ_profile is None:
            raise DomainError.not_found("Summarization model profile not found")
        if summ_profile.profile_kind.upper() not in _GENERATION_KINDS:
            raise DomainError("INVALID_MODEL_PROFILE_KIND", "summarization_model_profile_id must reference a generation model", 422)

        # Validate embedding model kind
        emb_profile = await profile_repo.find_by_id(tenant_id=tenant.tenant_id, profile_id=embedding_profile_id)
        if emb_profile is None:
            raise DomainError.not_found("Embedding model profile not found")
        if emb_profile.profile_kind.upper() not in _EMBEDDING_KINDS:
            raise DomainError("INVALID_MODEL_PROFILE_KIND", "embedding_profile_id must reference a dense embedding model", 422)

        repo = SqlAlchemyMemoryConfigRepository(self._session)
        return await repo.upsert(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            enabled=enabled,
            summarization_model_profile_id=summarization_model_profile_id,
            embedding_profile_id=embedding_profile_id,
            retention_days=retention_days,
            retrieval_top_k=retrieval_top_k,
            min_turns_to_summarize=min_turns_to_summarize,
            system_prompt=system_prompt,
        )

    async def delete(self, *, tenant: TenantContext, knowledge_base_id: str) -> bool:
        """Delete config and cascade-delete all memory chunks + Qdrant points for this KB."""
        self._require_legacy_kb_writes_enabled()
        from app.infrastructure.rag_catalog import (
            SqlAlchemyMemoryChunkRepository,
            SqlAlchemyMemoryConfigRepository,
        )

        config_repo = SqlAlchemyMemoryConfigRepository(self._session)
        config = await config_repo.find_by_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if config is None:
            raise DomainError.not_found("Memory config not found for this knowledge base")

        # Delete all memory chunks from DB (and Qdrant)
        chunk_repo = SqlAlchemyMemoryChunkRepository(self._session)
        # Use delete_by_knowledge_base which is not user-scoped
        # We need to get all chunks to collect point_ids — use a raw query approach
        # Actually delete_by_knowledge_base handles DB deletion; we just need point_ids first
        # Re-fetch without user filter
        from sqlalchemy import select

        from app.infrastructure.rag_catalog import MemoryChunkRecord

        result = await self._session.execute(
            select(MemoryChunkRecord).where(
                MemoryChunkRecord.tenant_id == tenant.tenant_id,
                MemoryChunkRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        chunks = result.scalars().all()
        point_ids = [c.qdrant_point_id for c in chunks]

        # Delete from Qdrant
        if point_ids:
            summarizer = MemorySummarizer(self._settings)
            try:
                await summarizer.delete_qdrant_points_by_ids(point_ids=point_ids)
            except Exception as e:
                logger.warning("[memory_config.delete] Qdrant deletion failed for kb=%s: %s", knowledge_base_id, e)

        # Delete chunks from DB
        await chunk_repo.delete_by_knowledge_base(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)

        # Delete config
        return await config_repo.delete(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)

    async def get_for_project(self, *, tenant: TenantContext, project_id: str) -> MemoryConfig:
        from app.infrastructure.rag_catalog import SqlAlchemyMemoryConfigRepository

        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id)
        if project is None or str(project.status) != "ACTIVE":
            raise DomainError.not_found("Project not found")
        config = await SqlAlchemyMemoryConfigRepository(self._session).find_by_project(tenant_id=tenant.tenant_id, project_id=project_id)
        if config is None:
            raise DomainError.not_found("Memory config not found for this Project")
        return config

    async def ensure_project(self, *, tenant: TenantContext, project_id: str) -> None:
        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id)
        if project is None or str(project.status) != "ACTIVE":
            raise DomainError.not_found("Project not found")

    async def upsert_for_project(
        self,
        *,
        tenant: TenantContext,
        project_id: str,
        enabled: bool,
        summarization_model_profile_id: str,
        embedding_profile_id: str,
        retention_days: int,
        retrieval_top_k: int,
        min_turns_to_summarize: int,
        system_prompt: str,
    ) -> MemoryConfig:
        if tenant.role is not UserRole.ADMIN:
            raise DomainError.forbidden("Project memory administration requires ADMIN access")
        from app.infrastructure.rag_catalog import SqlAlchemyMemoryConfigRepository, SqlAlchemyModelProfileRepository

        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id)
        if project is None or str(project.status) != "ACTIVE":
            raise DomainError.not_found("Project not found")
        if not (1 <= retention_days <= 365):
            raise DomainError.validation("retention_days must be between 1 and 365")
        if not (1 <= retrieval_top_k <= 20):
            raise DomainError.validation("retrieval_top_k must be between 1 and 20")
        if not (1 <= min_turns_to_summarize <= 20):
            raise DomainError.validation("min_turns_to_summarize must be between 1 and 20")
        if not validate_jinja2_template(system_prompt):
            raise DomainError("INVALID_PROMPT_TEMPLATE", "system_prompt is not a valid Jinja2 template", 422)
        profile_repo = SqlAlchemyModelProfileRepository(self._session)
        summ_profile = await profile_repo.find_by_id(tenant_id=tenant.tenant_id, profile_id=summarization_model_profile_id)
        if summ_profile is None:
            raise DomainError.not_found("Summarization model profile not found")
        if summ_profile.profile_kind.upper() not in _GENERATION_KINDS:
            raise DomainError("INVALID_MODEL_PROFILE_KIND", "summarization_model_profile_id must reference a generation model", 422)
        emb_profile = await profile_repo.find_by_id(tenant_id=tenant.tenant_id, profile_id=embedding_profile_id)
        if emb_profile is None:
            raise DomainError.not_found("Embedding model profile not found")
        if emb_profile.profile_kind.upper() not in _EMBEDDING_KINDS:
            raise DomainError("INVALID_MODEL_PROFILE_KIND", "embedding_profile_id must reference a dense embedding model", 422)
        return await SqlAlchemyMemoryConfigRepository(self._session).upsert_for_project(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            enabled=enabled,
            summarization_model_profile_id=summarization_model_profile_id,
            embedding_profile_id=embedding_profile_id,
            retention_days=retention_days,
            retrieval_top_k=retrieval_top_k,
            min_turns_to_summarize=min_turns_to_summarize,
            system_prompt=system_prompt,
        )

    async def delete_for_project(self, *, tenant: TenantContext, project_id: str) -> bool:
        if tenant.role is not UserRole.ADMIN:
            raise DomainError.forbidden("Project memory administration requires ADMIN access")
        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id)
        if project is None or str(project.status) != "ACTIVE":
            raise DomainError.not_found("Project not found")
        from app.infrastructure.rag_catalog import SqlAlchemyMemoryConfigRepository

        return await SqlAlchemyMemoryConfigRepository(self._session).delete_for_project(tenant_id=tenant.tenant_id, project_id=project_id)

    def get_defaults(self) -> dict[str, object]:
        return {
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "enabled": False,
            "retention_days": 90,
            "retrieval_top_k": 5,
            "min_turns_to_summarize": 3,
        }

    def _require_legacy_kb_writes_enabled(self) -> None:
        if not self._settings.rag_project_legacy_kb_writes_enabled:
            raise DomainError(
                "PROJECT_SCOPE_REQUIRED",
                "Project-scoped settings are required; Knowledge Base configuration writes are disabled",
                409,
            )
