"""Parallel dense/sparse retrieval with one immutable policy scope.

Sparse search is optional: if no sparse profile id is provided, only dense
search runs. Callers resolve profile ids from the active index profile.
"""

import asyncio

from app.core.settings import Settings
from app.domain.rag.adapter_ports import EmbeddingAdapter, SparseEncoderAdapter, VectorStoreAdapter
from app.domain.tenant_context import TenantContext


class RagHybridRetrievalService:
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingAdapter,
        sparse_encoder: SparseEncoderAdapter,
        vector_store: VectorStoreAdapter,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._sparse_encoder = sparse_encoder
        self._vector_store = vector_store

    async def retrieve(
        self,
        *,
        tenant: TenantContext,
        query: str,
        collection: str,
        knowledge_base_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
        embedding_profile_id: str,
        sparse_profile_id: str | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Return (dense_results, sparse_results). Sparse results empty when no sparse profile."""
        dense_vectors = await self._embeddings.embed(
            tenant=tenant, texts=[query], model_profile_id=embedding_profile_id
        )
        if len(dense_vectors) != 1:
            raise ValueError("Query embedding adapter must return exactly one vector")

        dense_task = self._vector_store.search_permitted(
            tenant=tenant,
            collection=collection,
            vector=dense_vectors[0],
            limit=self._settings.rag_retrieval_dense_candidates,
            knowledge_base_ids=knowledge_base_ids,
            active_generation_ids=active_generation_ids,
        )

        if not sparse_profile_id:
            return (await dense_task, [])

        sparse_vectors = await self._sparse_encoder.encode(
            tenant=tenant, texts=[query], sparse_profile_id=sparse_profile_id
        )
        if len(sparse_vectors) != 1:
            raise ValueError("Query sparse encoder must return exactly one sparse vector")
        sparse_results = await self._vector_store.search_sparse_permitted(
            tenant=tenant,
            collection=collection,
            vector=sparse_vectors[0],
            limit=self._settings.rag_retrieval_sparse_candidates,
            knowledge_base_ids=knowledge_base_ids,
            active_generation_ids=active_generation_ids,
        )
        return (await dense_task, sparse_results)
