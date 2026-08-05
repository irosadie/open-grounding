"""Chunk stage — split parsed text into chunks per active IndexProfile strategy."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.infrastructure.rag_catalog import (
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIndexProfileRepository,
)
from app.workers.stages.parse import _chunks_cache, _parsed_cache

logger = logging.getLogger(__name__)


async def chunk_document(
    document_version_id: str,
    tenant_id: str,
    session: AsyncSession,
    settings: Settings,
) -> list[str]:
    """Split parsed text into chunks using active IndexProfile strategy."""
    repo = SqlAlchemyDocumentVersionRepository(session)
    index_repo = SqlAlchemyIndexProfileRepository(session)

    await repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="CHUNKING"
    )

    # Get parsed text
    text = _parsed_cache.get(document_version_id)
    if not text:
        raise ValueError(f"No parsed text found for {document_version_id}. Parse stage must run first.")

    # Get active index profile for chunking config
    index_profile = await index_repo.find_active(tenant_id=tenant_id)
    if index_profile is None:
        raise ValueError("No active index profile found. Set one in Settings → Index Profiles.")

    strategy = index_profile.chunking_strategy or "RECURSIVE"
    chunk_size = index_profile.chunk_size_tokens or 400
    overlap = index_profile.chunk_overlap_tokens or 50

    chunks = _split_text(text, strategy=strategy, chunk_size=chunk_size, overlap=overlap)

    _chunks_cache[document_version_id] = chunks

    logger.info("[chunk] %d chunks from %s (strategy=%s, size=%d)", len(chunks), document_version_id, strategy, chunk_size)
    return chunks


def _split_text(text: str, strategy: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into chunks using the specified strategy."""
    # Approximate token count: 1 token ≈ 4 chars
    char_size = chunk_size * 4
    char_overlap = overlap * 4

    if strategy in ("RECURSIVE", "PARAGRAPH"):
        return _recursive_split(text, char_size, char_overlap)
    elif strategy == "SENTENCE":
        return _sentence_split(text, char_size, char_overlap)
    else:  # FIXED
        return _fixed_split(text, char_size, char_overlap)


def _recursive_split(text: str, size: int, overlap: int) -> list[str]:
    """Recursive character text splitter — respects paragraph/sentence boundaries."""
    separators = ["\n\n", "\n", ". ", " ", ""]
    return _split_with_separators(text, separators, size, overlap)


def _sentence_split(text: str, size: int, overlap: int) -> list[str]:
    separators = [". ", "! ", "? ", "\n", " ", ""]
    return _split_with_separators(text, separators, size, overlap)


def _fixed_split(text: str, size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def _split_with_separators(text: str, separators: list[str], size: int, overlap: int) -> list[str]:
    """Split text recursively using a list of separators."""
    if len(text) <= size:
        return [text.strip()] if text.strip() else []

    for sep in separators:
        if sep and sep in text:
            parts = text.split(sep)
            chunks = []
            current = ""
            for part in parts:
                candidate = current + sep + part if current else part
                if len(candidate) > size and current:
                    if current.strip():
                        chunks.append(current.strip())
                    current = part
                else:
                    current = candidate
            if current.strip():
                chunks.append(current.strip())

            # Apply overlap
            if overlap > 0 and len(chunks) > 1:
                overlapped = [chunks[0]]
                for i in range(1, len(chunks)):
                    prev_tail = chunks[i - 1][-overlap:]
                    overlapped.append(prev_tail + " " + chunks[i])
                return [c for c in overlapped if c.strip()]
            return [c for c in chunks if c.strip()]

    return _fixed_split(text, size, overlap)
