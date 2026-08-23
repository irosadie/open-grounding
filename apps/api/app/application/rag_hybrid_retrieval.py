"""Parallel dense/sparse retrieval with one immutable policy scope.

Sparse search is optional: if no sparse profile id is provided, only dense
search runs. Callers resolve profile ids from the active index profile.
"""

import asyncio

from app.application.retrieval_fusion import rrf_fuse
from app.core.settings import Settings
from app.domain.rag.adapter_ports import EmbeddingAdapter, SparseEncoderAdapter, VectorStoreAdapter
from app.domain.rag.profiles import RetrievalConfig
from app.domain.rag.repositories import RetrievalConfigRepository
from app.domain.tenant_context import TenantContext


class RagHybridRetrievalService:
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingAdapter,
        sparse_encoder: SparseEncoderAdapter,
        vector_store: VectorStoreAdapter,
        config_loader: RetrievalConfigRepository | None = None,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._sparse_encoder = sparse_encoder
        self._vector_store = vector_store
        self._config_loader = config_loader

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
        index_profile_id: str | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Return fused results in the first slot and preserve the legacy tuple shape."""
        config = RetrievalConfig.defaults(index_profile_id or "")
        if self._config_loader is not None and index_profile_id:
            config = await self._config_loader.find_by_profile(tenant_id=tenant.tenant_id, index_profile_id=index_profile_id) or config
        dense_vectors, sparse_vectors = await asyncio.gather(
            self._embeddings.embed(tenant=tenant, texts=[query], model_profile_id=embedding_profile_id),
            self._sparse_encoder.encode(tenant=tenant, texts=[query], sparse_profile_id=sparse_profile_id) if sparse_profile_id and config.enabled else asyncio.sleep(0, result=[]),
        )
        if len(dense_vectors) != 1:
            raise ValueError("Query embedding adapter must return exactly one vector")
        dense_task = self._vector_store.search_permitted(
            tenant=tenant,
            collection=collection,
            vector=dense_vectors[0],
            limit=config.dense_candidates,
            knowledge_base_ids=knowledge_base_ids,
            active_generation_ids=active_generation_ids,
        )
        if not sparse_vectors:
            dense_results = await dense_task
            return ([result for result in dense_results[: config.fused_candidates]], [])
        if len(sparse_vectors) != 1:
            raise ValueError("Query sparse encoder must return exactly one sparse vector")
        dense_results, sparse_results = await asyncio.gather(
            dense_task,
            self._vector_store.search_sparse_permitted(
                tenant=tenant,
                collection=collection,
                vector=sparse_vectors[0],
                limit=config.sparse_candidates,
                knowledge_base_ids=knowledge_base_ids,
                active_generation_ids=active_generation_ids,
            ),
        )
        fused = rrf_fuse(
            dense_results,
            sparse_results,
            k=config.fusion_k,
            dense_weight=config.dense_weight,
            sparse_weight=config.sparse_weight,
            cap=config.fused_candidates,
        )
        return ([{**result.candidate, "id": result.id, "score": result.score} for result in fused], [])
