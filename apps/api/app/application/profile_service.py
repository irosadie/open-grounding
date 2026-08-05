"""Application service for model and index profile management."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.domain.rag.profiles import IndexProfile, ModelProfile
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import (
    SqlAlchemyIndexProfileRepository,
    SqlAlchemyModelProfileRepository,
)


@dataclass(frozen=True)
class ModelProfileResult:
    id: str
    tenant_id: str
    name: str
    profile_kind: str
    provider: str
    model: str
    modality: str
    dimensions: int | None
    version: str
    is_active: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class IndexProfileResult:
    id: str
    tenant_id: str
    name: str
    embedding_profile_id: str
    sparse_profile_id: str | None
    reranker_profile_id: str | None
    collection: str
    dimensions: int
    distance_metric: str
    chunking_strategy: str
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    parent_chunk_size: int
    version: str
    is_active: bool
    created_at: str
    updated_at: str


def _mp_to_result(mp: ModelProfile) -> ModelProfileResult:
    return ModelProfileResult(
        id=mp.id,
        tenant_id=mp.tenant_id,
        name=mp.name,
        profile_kind=mp.profile_kind,
        provider=mp.provider,
        model=mp.model,
        modality=mp.modality,
        dimensions=mp.dimensions,
        version=mp.version,
        is_active=mp.is_active,
        created_at=mp.created_at,
        updated_at=mp.updated_at,
    )


def _ip_to_result(ip: IndexProfile) -> IndexProfileResult:
    return IndexProfileResult(
        id=ip.id,
        tenant_id=ip.tenant_id,
        name=ip.name,
        embedding_profile_id=ip.embedding_profile_id,
        sparse_profile_id=ip.sparse_profile_id,
        reranker_profile_id=ip.reranker_profile_id,
        collection=ip.collection,
        dimensions=ip.dimensions,
        distance_metric=ip.distance_metric,
        chunking_strategy=ip.chunking_strategy,
        chunk_size_tokens=ip.chunk_size_tokens,
        chunk_overlap_tokens=ip.chunk_overlap_tokens,
        parent_chunk_size=ip.parent_chunk_size,
        version=ip.version,
        is_active=ip.is_active,
        created_at=ip.created_at,
        updated_at=ip.updated_at,
    )


class ModelProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = SqlAlchemyModelProfileRepository(session)

    async def create(
        self,
        *,
        tenant: TenantContext,
        name: str,
        profile_kind: str,
        provider: str,
        model: str,
        modality: str = "TEXT",
        dimensions: int | None = None,
        config_json: str | None = None,
    ) -> ModelProfileResult:
        valid_kinds = {"DENSE_EMBEDDING", "SPARSE_EMBEDDING", "RERANKER", "GENERATION"}
        if profile_kind not in valid_kinds:
            raise DomainError("VALIDATION_ERROR", f"profile_kind must be one of {valid_kinds}", 422)
        mp = await self._repo.create(
            tenant_id=tenant.tenant_id,
            name=name,
            profile_kind=profile_kind,
            provider=provider,
            model=model,
            modality=modality,
            dimensions=dimensions,
            config_json=config_json,
            version="v1",
        )
        return _mp_to_result(mp)

    async def list_all(self, *, tenant: TenantContext) -> list[ModelProfileResult]:
        profiles = await self._repo.list_by_tenant(tenant_id=tenant.tenant_id)
        return [_mp_to_result(p) for p in profiles]

    async def archive(self, *, tenant: TenantContext, profile_id: str) -> ModelProfileResult:
        mp = await self._repo.archive(tenant_id=tenant.tenant_id, profile_id=profile_id)
        if mp is None:
            raise DomainError("NOT_FOUND", "Model profile not found", 404)
        return _mp_to_result(mp)


class IndexProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = SqlAlchemyIndexProfileRepository(session)
        self._mp_repo = SqlAlchemyModelProfileRepository(session)

    async def create(
        self,
        *,
        tenant: TenantContext,
        name: str,
        embedding_profile_id: str,
        sparse_profile_id: str | None,
        reranker_profile_id: str | None,
        collection: str,
        dimensions: int,
        distance_metric: str,
        chunking_strategy: str = "RECURSIVE",
        chunk_size_tokens: int = 400,
        chunk_overlap_tokens: int = 50,
        parent_chunk_size: int = 1500,
    ) -> IndexProfileResult:
        # Validate embedding profile exists
        emb = await self._mp_repo.find_by_id(
            tenant_id=tenant.tenant_id, profile_id=embedding_profile_id
        )
        if emb is None:
            raise DomainError("NOT_FOUND", "Embedding model profile not found", 404)
        if emb.dimensions is not None and emb.dimensions != dimensions:
            raise DomainError(
                "VALIDATION_ERROR",
                f"Dimensions {dimensions} do not match embedding model dimensions {emb.dimensions}",
                422,
            )
        ip = await self._repo.create(
            tenant_id=tenant.tenant_id,
            name=name,
            embedding_profile_id=embedding_profile_id,
            sparse_profile_id=sparse_profile_id,
            reranker_profile_id=reranker_profile_id,
            collection=collection,
            dimensions=dimensions,
            distance_metric=distance_metric,
            chunking_strategy=chunking_strategy,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            parent_chunk_size=parent_chunk_size,
            version="v1",
            is_active=False,
        )
        return _ip_to_result(ip)

    async def list_all(self, *, tenant: TenantContext) -> list[IndexProfileResult]:
        profiles = await self._repo.list_by_tenant(tenant_id=tenant.tenant_id)
        return [_ip_to_result(p) for p in profiles]

    async def set_active(self, *, tenant: TenantContext, profile_id: str) -> IndexProfileResult:
        ip = await self._repo.set_active(tenant_id=tenant.tenant_id, profile_id=profile_id)
        if ip is None:
            raise DomainError("NOT_FOUND", "Index profile not found", 404)
        return _ip_to_result(ip)
