"""Unit tests for MemoryRetriever."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.memory_retriever import MemoryRetriever, _empty_result, _format_context_block


def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.qdrant_url = "http://qdrant:6333"
    settings.qdrant_api_key = None
    return settings


def _make_config(enabled: bool = True, top_k: int = 5) -> MagicMock:
    config = MagicMock()
    config.enabled = enabled
    config.retrieval_top_k = top_k
    config.embedding_profile_id = "emb-1"
    return config


def test_empty_result_shape() -> None:
    result = _empty_result()
    assert result["triggered"] is False
    assert result["chunks_retrieved"] == 0
    assert result["context_block"] is None


def test_format_context_block() -> None:
    block = _format_context_block(["mem 1", "mem 2"])
    assert "[Relevant context from prior conversations:]" in block
    assert "- mem 1" in block
    assert "- mem 2" in block


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_config_disabled() -> None:
    retriever = MemoryRetriever(_make_settings())
    session = MagicMock()
    config_repo = AsyncMock()
    config_repo.find_by_knowledge_base.return_value = _make_config(enabled=False)

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_repo_cls:
        cfg_repo_cls.return_value = config_repo
        result = await retriever.retrieve(
            query="test", tenant_id="t", knowledge_base_id="kb", user_id="u", session=session,
        )
    assert result["triggered"] is False


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_config_missing() -> None:
    retriever = MemoryRetriever(_make_settings())
    session = MagicMock()
    config_repo = AsyncMock()
    config_repo.find_by_knowledge_base.return_value = None

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as mock_repo:
        mock_repo.return_value = config_repo
        result = await retriever.retrieve(
            query="test", tenant_id="t", knowledge_base_id="kb", user_id="u", session=session,
        )
    assert result["triggered"] is False


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_no_chunks_fast_path() -> None:
    retriever = MemoryRetriever(_make_settings())
    session = MagicMock()
    config_repo = AsyncMock()
    config_repo.find_by_knowledge_base.return_value = _make_config(enabled=True)
    chunk_repo = AsyncMock()
    chunk_repo.count_by_user_kb.return_value = 0

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_cls:
        cfg_cls.return_value = config_repo
        chunk_cls.return_value = chunk_repo
        result = await retriever.retrieve(
            query="test", tenant_id="t", knowledge_base_id="kb", user_id="u", session=session,
        )
    assert result["triggered"] is False


@pytest.mark.asyncio
async def test_retrieve_never_raises_on_failure() -> None:
    retriever = MemoryRetriever(_make_settings())
    session = MagicMock()

    with patch.object(retriever, "_retrieve_inner", side_effect=Exception("boom")):
        result = await retriever.retrieve(
            query="test", tenant_id="t", knowledge_base_id="kb", user_id="u", session=session,
        )
    assert result["triggered"] is False


@pytest.mark.asyncio
async def test_retrieve_timeout_returns_empty() -> None:
    import asyncio
    retriever = MemoryRetriever(_make_settings())
    session = MagicMock()

    async def _slow():
        await asyncio.sleep(10)

    with patch.object(retriever, "_retrieve_inner", new=_slow):
        result = await retriever.retrieve(
            query="test", tenant_id="t", knowledge_base_id="kb", user_id="u", session=session,
        )
    assert result["triggered"] is False


@pytest.mark.asyncio
async def test_retrieve_returns_summaries_and_context() -> None:
    retriever = MemoryRetriever(_make_settings())
    session = MagicMock()
    config_repo = AsyncMock()
    config_repo.find_by_knowledge_base.return_value = _make_config(enabled=True, top_k=5)
    chunk_repo = AsyncMock()
    chunk_repo.count_by_user_kb.return_value = 2

    point = {"payload": {"chunk_id": "chunk-1"}}
    httpx_client = AsyncMock()
    http_resp = MagicMock()
    http_resp.json.return_value = {"result": {"points": [point]}}
    httpx_client.__aenter__.return_value.post.return_value = http_resp

    profile_repo = AsyncMock()
    profile_repo.find_by_id.return_value = MagicMock(provider="fastembed", model="bge")

    existing_chunk = MagicMock()
    existing_chunk.summary = "memory summary"
    existing_chunk.created_at = datetime.now(UTC).replace(tzinfo=None)
    chunk_repo.find_by_id.return_value = existing_chunk

    registry = MagicMock()
    registry.embed_with_fallback = AsyncMock(return_value=[[0.1]])

    with patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as cfg_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryChunkRepository") as chunk_cls, \
         patch("app.infrastructure.rag_catalog.SqlAlchemyModelProfileRepository") as prof_cls, \
         patch("app.infrastructure.providers.registry.ProviderRegistry") as reg_cls, \
         patch("httpx.AsyncClient") as client_cls:
        cfg_cls.return_value = config_repo
        chunk_cls.return_value = chunk_repo
        prof_cls.return_value = profile_repo
        reg_cls.return_value = registry
        client_cls.return_value = httpx_client

        result = await retriever.retrieve(
            query="test", tenant_id="t", knowledge_base_id="kb", user_id="u", session=session,
        )

    assert result["triggered"] is True
    assert result["chunks_retrieved"] == 1
    assert "memory summary" in (result["context_block"] or "")