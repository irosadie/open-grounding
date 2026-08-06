"""Memory configuration service — create/get/delete with validation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.memory_summarizer import MemorySummarizer, validate_jinja2_template
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.rag.memory import DEFAULT_SYSTEM_PROMPT, MemoryConfig
from app.domain.tenant_context import TenantContext

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_GENERATION_KINDS = {"GENERATION", "CHAT"}
_EMBEDDING_KINDS = {"EMBEDDING", "DENSE_EMBEDDING"}


class MemoryConfigService:
    def __init__(self, session: "AsyncSession", settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def get(self, *, tenant: TenantContext, knowledge_base_id: str) -> MemoryConfig:
        from app.infrastructure.rag_catalog import SqlAlchemyMemoryConfigRepository
        repo = SqlAlchemyMemoryConfigRepository(self._session)
        config = await repo.find_by_knowledge_base(
            tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id
        )
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
        summ_profile = await profile_repo.find_by_id(
            tenant_id=tenant.tenant_id, profile_id=summarization_model_profile_id
        )
        if summ_profile is None:
            raise DomainError.not_found("Summarization model profile not found")
        if summ_profile.profile_kind.upper() not in _GENERATION_KINDS:
            raise DomainError("INVALID_MODEL_PROFILE_KIND", "summarization_model_profile_id must reference a generation model", 422)

        # Validate embedding model kind
        emb_profile = await profile_repo.find_by_id(
            tenant_id=tenant.tenant_id, profile_id=embedding_profile_id
        )
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
        from app.infrastructure.rag_catalog import (
            SqlAlchemyMemoryChunkRepository,
            SqlAlchemyMemoryConfigRepository,
        )

        config_repo = SqlAlchemyMemoryConfigRepository(self._session)
        config = await config_repo.find_by_knowledge_base(
            tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id
        )
        if config is None:
            raise DomainError.not_found("Memory config not found for this knowledge base")

        # Delete all memory chunks from DB (and Qdrant)
        chunk_repo = SqlAlchemyMemoryChunkRepository(self._session)
        # Collect all chunks for Qdrant deletion
        all_chunks = await chunk_repo.find_by_user_kb(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            user_id="",  # not user-scoped here — need a different method
            page=1,
            page_size=10000,
        )
        # Use delete_by_knowledge_base which is not user-scoped
        point_ids = []
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
        await chunk_repo.delete_by_knowledge_base(
            tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id
        )

        # Delete config
        return await config_repo.delete(
            tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id
        )

    def get_defaults(self) -> dict[str, object]:
        return {
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "enabled": False,
            "retention_days": 90,
            "retrieval_top_k": 5,
            "min_turns_to_summarize": 3,
        }
