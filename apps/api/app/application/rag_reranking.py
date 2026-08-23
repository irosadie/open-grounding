"""Bounded reranking that preserves the pre-filtered candidate set."""

import asyncio

from app.core.settings import Settings
from app.domain.rag.adapter_ports import RerankerAdapter
from app.domain.tenant_context import TenantContext


class RagRerankingService:
    def __init__(self, settings: Settings, reranker: RerankerAdapter) -> None:
        self._settings = settings
        self._reranker = reranker

    async def rerank(
        self, *, tenant: TenantContext, query: str, candidates: list[dict[str, object]], profile_id: str
    ) -> tuple[list[dict[str, object]], bool]:
        bounded = candidates[: self._settings.rag_retrieval_reranker_candidates]
        try:
            ranked = await asyncio.wait_for(
                self._reranker.rerank(
                    tenant=tenant,
                    query=query,
                    candidates=bounded,
                    reranker_profile_id=profile_id,
                    top_k=len(bounded),
                ),
                timeout=self._settings.rag_retrieval_timeout_seconds,
            )
        except (TimeoutError, RuntimeError):
            return bounded, True
        allowed_ids = {str(candidate["id"]) for candidate in bounded}
        safe_ranked = [candidate for candidate in ranked if str(candidate.get("id")) in allowed_ids]
        return safe_ranked, False
