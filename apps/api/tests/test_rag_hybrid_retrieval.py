from uuid import uuid4

import pytest

from app.application.rag_hybrid_retrieval import RagHybridRetrievalService
from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.rag.profiles import RetrievalConfig
from app.domain.tenant_context import TenantContext


class EmbeddingsStub:
    async def embed(self, *, tenant: TenantContext, texts: list[str], model_profile_id: str) -> list[list[float]]:
        del tenant, texts
        assert model_profile_id == "embedding-v1"
        return [[0.1, 0.2]]


class SparseStub:
    async def encode(self, *, tenant: TenantContext, texts: list[str], sparse_profile_id: str) -> list[dict[str, object]]:
        del tenant, texts
        assert sparse_profile_id == "sparse-v1"
        return [{"indices": [1], "values": [0.5]}]


class VectorStoreStub:
    def __init__(self) -> None:
        self.scopes: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    async def search_permitted(
        self,
        *,
        tenant: TenantContext,
        collection: str,
        vector: list[float],
        limit: int,
        knowledge_base_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
    ) -> list[dict[str, object]]:
        del tenant, collection, vector, limit
        self.scopes.append((knowledge_base_ids, active_generation_ids))
        return [{"id": "dense"}]

    async def search_sparse_permitted(
        self,
        *,
        tenant: TenantContext,
        collection: str,
        vector: dict[str, object],
        limit: int,
        knowledge_base_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
    ) -> list[dict[str, object]]:
        del tenant, collection, vector, limit
        self.scopes.append((knowledge_base_ids, active_generation_ids))
        return [{"id": "sparse"}]


class SparseOnlyVectorStoreStub(VectorStoreStub):
    async def search_permitted(
        self,
        *,
        tenant: TenantContext,
        collection: str,
        vector: list[float],
        limit: int,
        knowledge_base_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
    ) -> list[dict[str, object]]:
        del tenant, collection, vector, limit, knowledge_base_ids, active_generation_ids
        return []


class RetrievalConfigStub:
    async def find_by_profile(self, *, tenant_id: str, index_profile_id: str) -> RetrievalConfig:
        assert tenant_id
        assert index_profile_id == "index-v1"
        return RetrievalConfig(
            index_profile_id=index_profile_id,
            dense_weight=0.1,
            sparse_weight=5.0,
            fusion_k=1,
            dense_candidates=50,
            sparse_candidates=50,
            fused_candidates=40,
            enabled=True,
        )


@pytest.mark.asyncio
async def test_hybrid_retrieval_uses_identical_policy_scope_for_dense_and_sparse() -> None:
    tenant = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)
    settings = Settings(_env_file=None)
    vector_store = VectorStoreStub()
    service = RagHybridRetrievalService(settings, EmbeddingsStub(), SparseStub(), vector_store)

    dense, sparse = await service.retrieve(
        tenant=tenant,
        query="question",
        collection="rag",
        knowledge_base_ids=("kb-1",),
        active_generation_ids=("generation-1",),
        embedding_profile_id="embedding-v1",
        sparse_profile_id="sparse-v1",
    )

    assert [item["id"] for item in dense] == ["dense", "sparse"]
    assert sparse == []
    assert vector_store.scopes == [(("kb-1",), ("generation-1",))] * 2


@pytest.mark.asyncio
async def test_hybrid_retrieval_without_sparse_returns_only_dense() -> None:
    tenant = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)
    settings = Settings(_env_file=None)
    vector_store = VectorStoreStub()
    service = RagHybridRetrievalService(settings, EmbeddingsStub(), SparseStub(), vector_store)

    dense, sparse = await service.retrieve(
        tenant=tenant,
        query="question",
        collection="rag",
        knowledge_base_ids=("kb-1",),
        active_generation_ids=("generation-1",),
        embedding_profile_id="embedding-v1",
        sparse_profile_id=None,
    )

    assert dense == [{"id": "dense"}]
    assert sparse == []
    assert len(vector_store.scopes) == 1


@pytest.mark.asyncio
async def test_hybrid_retrieval_returns_sparse_hit_when_dense_misses() -> None:
    tenant = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)
    service = RagHybridRetrievalService(Settings(_env_file=None), EmbeddingsStub(), SparseStub(), SparseOnlyVectorStoreStub())

    fused, sparse = await service.retrieve(
        tenant=tenant,
        query="keyword",
        collection="rag",
        knowledge_base_ids=("kb-1",),
        active_generation_ids=("generation-1",),
        embedding_profile_id="embedding-v1",
        sparse_profile_id="sparse-v1",
    )

    assert [item["id"] for item in fused] == ["sparse"]
    assert sparse == []


@pytest.mark.asyncio
async def test_sparse_weight_prioritizes_lexical_keyword_evidence() -> None:
    tenant = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)
    vector_store = VectorStoreStub()
    service = RagHybridRetrievalService(Settings(_env_file=None), EmbeddingsStub(), SparseStub(), vector_store, RetrievalConfigStub())

    fused, _ = await service.retrieve(
        tenant=tenant,
        query="rare-keyword-42",
        collection="rag",
        knowledge_base_ids=("kb-1",),
        active_generation_ids=("generation-1",),
        embedding_profile_id="embedding-v1",
        sparse_profile_id="sparse-v1",
        index_profile_id="index-v1",
    )

    assert [item["id"] for item in fused] == ["sparse", "dense"]
