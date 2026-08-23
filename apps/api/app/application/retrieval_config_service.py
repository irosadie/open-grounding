"""Application service for validated per-index-profile retrieval settings."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.rag.profiles import RetrievalConfig
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import SqlAlchemyIndexProfileRepository, SqlAlchemyRetrievalConfigRepository


class RetrievalConfigService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._repo = SqlAlchemyRetrievalConfigRepository(session)
        self._profile_repo = SqlAlchemyIndexProfileRepository(session)

    async def get(self, *, tenant: TenantContext, index_profile_id: str) -> RetrievalConfig:
        config = await self._repo.find_by_profile(tenant_id=tenant.tenant_id, index_profile_id=index_profile_id)
        return config or RetrievalConfig.defaults(index_profile_id)

    async def upsert(
        self,
        *,
        tenant: TenantContext,
        index_profile_id: str,
        dense_weight: float,
        sparse_weight: float,
        fusion_k: int,
        dense_candidates: int,
        sparse_candidates: int,
        fused_candidates: int,
        enabled: bool,
    ) -> RetrievalConfig:
        if await self._profile_repo.find_by_id(tenant_id=tenant.tenant_id, profile_id=index_profile_id) is None:
            raise DomainError("INDEX_PROFILE_NOT_FOUND", "Index profile not found", 404)
        if not 0.0 <= dense_weight <= 5.0 or not 0.0 <= sparse_weight <= 5.0:
            raise DomainError("VALIDATION_ERROR", "Retrieval weights must be between 0.0 and 5.0", 422)
        for name, value in (("fusion_k", fusion_k), ("dense_candidates", dense_candidates), ("sparse_candidates", sparse_candidates), ("fused_candidates", fused_candidates)):
            if not 1 <= value <= 200:
                raise DomainError("VALIDATION_ERROR", f"{name} must be between 1 and 200", 422)
        return await self._repo.upsert(
            tenant_id=tenant.tenant_id, index_profile_id=index_profile_id,
            dense_weight=dense_weight, sparse_weight=sparse_weight, fusion_k=fusion_k,
            dense_candidates=dense_candidates, sparse_candidates=sparse_candidates,
            fused_candidates=fused_candidates, enabled=enabled,
        )

    async def delete(self, *, tenant: TenantContext, index_profile_id: str) -> bool:
        return await self._repo.delete(tenant_id=tenant.tenant_id, index_profile_id=index_profile_id)
