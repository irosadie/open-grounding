"""Query-time memory retrieval: embed query → search Qdrant memory collection → return summaries."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.settings import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_QDRANT_MEMORY_COLLECTION = "memory"
_RETRIEVAL_TIMEOUT_S = 2


class MemoryRetriever:
    """Fast-path memory retrieval with 2s timeout and silent fallback on failure."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def retrieve(
        self,
        *,
        query: str,
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
        session: "AsyncSession",
    ) -> dict[str, object]:
        """Retrieve relevant memory chunks for a query. Never raises — returns empty on failure."""
        try:
            return await asyncio.wait_for(
                self._retrieve_inner(
                    query=query,
                    tenant_id=tenant_id,
                    knowledge_base_id=knowledge_base_id,
                    user_id=user_id,
                    session=session,
                ),
                timeout=_RETRIEVAL_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning("[memory.retrieve] timeout for kb=%s user=%s", knowledge_base_id, user_id)
            return _empty_result()
        except Exception as e:
            logger.warning("[memory.retrieve] failed for kb=%s user=%s: %s", knowledge_base_id, user_id, e)
            return _empty_result()

    async def _retrieve_inner(
        self,
        *,
        query: str,
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
        session: "AsyncSession",
    ) -> dict[str, object]:
        from app.infrastructure.rag_catalog import (
            SqlAlchemyMemoryChunkRepository,
            SqlAlchemyMemoryConfigRepository,
            SqlAlchemyModelProfileRepository,
        )
        from app.infrastructure.providers.registry import ProviderRegistry

        # 1. Load config
        config_repo = SqlAlchemyMemoryConfigRepository(session)
        config = await config_repo.find_by_knowledge_base(
            tenant_id=tenant_id, knowledge_base_id=knowledge_base_id
        )
        if config is None or not config.enabled:
            return _empty_result()

        # 2. Fast-path: skip Qdrant if user has no chunks for this KB
        chunk_repo = SqlAlchemyMemoryChunkRepository(session)
        count = await chunk_repo.count_by_user_kb(
            tenant_id=tenant_id, knowledge_base_id=knowledge_base_id, user_id=user_id
        )
        if count == 0:
            return _empty_result()

        # 3. Embed the query
        profile_repo = SqlAlchemyModelProfileRepository(session)
        profile = await profile_repo.find_by_id(
            tenant_id=tenant_id, profile_id=config.embedding_profile_id
        )
        if profile is None:
            return _empty_result()

        registry = ProviderRegistry(self._settings)
        vectors = await registry.embed_with_fallback(
            texts=[query],
            primary_provider=profile.provider,
            primary_model=profile.model,
            tenant_id=tenant_id,
            session=session,
        )
        query_vector = vectors[0]

        # 4. Search Qdrant memory collection
        now_iso = datetime.now(UTC).replace(tzinfo=None).isoformat()
        qdrant_filter = {
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}},
                {"key": "knowledge_base_id", "match": {"value": knowledge_base_id}},
                {"key": "user_id", "match": {"value": user_id}},
                {"key": "expires_at", "range": {"gt": now_iso}},
            ]
        }
        import httpx
        base_url = self._settings.qdrant_url.rstrip("/")
        headers = {"api-key": self._settings.qdrant_api_key} if self._settings.qdrant_api_key else {}
        async with httpx.AsyncClient(timeout=_RETRIEVAL_TIMEOUT_S) as client:
            resp = await client.post(
                f"{base_url}/collections/{_QDRANT_MEMORY_COLLECTION}/points/query",
                headers=headers,
                json={
                    "query": query_vector,
                    "limit": config.retrieval_top_k,
                    "filter": qdrant_filter,
                    "with_payload": True,
                },
            )
            resp.raise_for_status()
            result = resp.json().get("result", {})
            points = result.get("points", []) if isinstance(result, dict) else []

        if not points:
            return _empty_result()

        # 5. Fetch summaries from DB by chunk_ids from Qdrant payload
        chunk_ids = [
            p["payload"]["chunk_id"]
            for p in points
            if isinstance(p.get("payload"), dict) and "chunk_id" in p["payload"]
        ]
        summaries: list[str] = []
        oldest_age_days: int | None = None
        now_naive = datetime.now(UTC).replace(tzinfo=None)

        for chunk_id in chunk_ids:
            chunk = await chunk_repo.find_by_id(tenant_id=tenant_id, chunk_id=chunk_id)
            if chunk:
                summaries.append(chunk.summary)
                age_days = (now_naive - chunk.created_at).days
                if oldest_age_days is None or age_days > oldest_age_days:
                    oldest_age_days = age_days

        if not summaries:
            return _empty_result()

        return {
            "triggered": True,
            "chunks_retrieved": len(summaries),
            "oldest_memory_age_days": oldest_age_days or 0,
            "context_block": _format_context_block(summaries),
        }


def _empty_result() -> dict[str, object]:
    return {
        "triggered": False,
        "chunks_retrieved": 0,
        "oldest_memory_age_days": None,
        "context_block": None,
    }


def _format_context_block(summaries: list[str]) -> str:
    lines = "\n".join(f"- {s}" for s in summaries)
    return f"[Relevant context from prior conversations:]\n{lines}"
