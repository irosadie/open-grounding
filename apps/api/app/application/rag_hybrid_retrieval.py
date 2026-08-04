"""Parallel dense/sparse retrieval with one immutable policy scope."""

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
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        embedding_profile_id = self._required_profile_id(self._settings.rag_query_embedding_profile_id, "embedding")
        sparse_profile_id = self._required_profile_id(self._settings.rag_query_sparse_profile_id, "sparse")
        dense_vectors, sparse_vectors = await asyncio.gather(
            self._embeddings.embed(tenant=tenant, texts=[query], model_profile_id=embedding_profile_id),
            self._sparse_encoder.encode(tenant=tenant, texts=[query], sparse_profile_id=sparse_profile_id),
        )
        if len(dense_vectors) != 1 or len(sparse_vectors) != 1:
            raise ValueError("Query representation adapters must return exactly one vector")
        return await asyncio.gather(
            self._vector_store.search_permitted(
                tenant=tenant,
                collection=collection,
                vector=dense_vectors[0],
                limit=self._settings.rag_retrieval_dense_candidates,
                knowledge_base_ids=knowledge_base_ids,
                active_generation_ids=active_generation_ids,
            ),
            self._vector_store.search_sparse_permitted(
                tenant=tenant,
                collection=collection,
                vector=sparse_vectors[0],
                limit=self._settings.rag_retrieval_sparse_candidates,
                knowledge_base_ids=knowledge_base_ids,
                active_generation_ids=active_generation_ids,
            ),
        )

    @staticmethod
    def _required_profile_id(profile_id: str | None, profile_kind: str) -> str:
        if not profile_id:
            raise ValueError(f"Active {profile_kind} profile is required for retrieval")
        return profile_id
