"""Structure-aware parent-child chunking.

Produces parent context units (~1,000-2,000 tokens) and embedded child
retrieval units (~300-500 tokens, hard max 700) from canonical
``DocumentElement`` records. Structural boundaries (titles, code, lists) are
respected — no arbitrary global overlap. Only a single oversized element is
split with overlap.

Chunk IDs are deterministic hashes of version, hierarchy path, offsets,
content type, and chunker version, so retries never create duplicate chunks.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field

from app.domain.rag.elements import DocumentElement, ElementType, ParsedDocument


@dataclass(frozen=True)
class ChunkResult:
    """A parent or child chunk ready for persistence."""

    id: str
    chunk_type: str
    parent_id: str | None
    hierarchy_path: tuple[str, ...]
    page: int | None
    content_type: str
    text: str
    token_count: int
    source_offsets_start: int | None
    source_offsets_end: int | None


@dataclass(frozen=True)
class ChunkManifest:
    """Result of chunking: ordered parent and child chunks."""

    chunks: list[ChunkResult] = field(default_factory=list)


TokenCounter = Callable[[str], int]


def default_token_counter(text: str) -> int:
    """Approximate token count as ~4 chars per token (fallback)."""
    return max(1, len(text) // 4)


def _deterministic_chunk_id(
    *, version: str, hierarchy_path: tuple[str, ...], text: str,
    content_type: str, chunker_version: str, chunk_index: int,
) -> str:
    raw = f"{version}:{'/'.join(hierarchy_path)}:{chunk_index}:{content_type}:{chunker_version}:{text[:200]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _is_boundary(element: DocumentElement) -> bool:
    return element.type in (ElementType.TITLE, ElementType.CODE, ElementType.LIST, ElementType.TABLE, ElementType.FORMULA)


def chunk_document(
    doc: ParsedDocument,
    *,
    chunker_version: str = "1",
    child_token_max: int = 500,
    child_token_min: int = 300,
    child_token_hard_max: int = 700,
    parent_token_max: int = 2000,
    token_counter: TokenCounter = default_token_counter,
) -> ChunkManifest:
    """Chunk a parsed document into parent-child units respecting boundaries."""
    chunks: list[ChunkResult] = []
    parent_buffer: list[DocumentElement] = []
    parent_tokens = 0
    parent_idx = 0
    child_idx = 0

    def _flush_parent() -> None:
        nonlocal parent_buffer, parent_tokens, parent_idx, child_idx
        if not parent_buffer:
            return
        ptext = "\n\n".join(e.text for e in parent_buffer)
        ptokens = token_counter(ptext)
        ppath = parent_buffer[0].hierarchy_path
        ppage = parent_buffer[0].page
        pctype = parent_buffer[0].type
        pid = _deterministic_chunk_id(
            version=chunker_version, hierarchy_path=ppath, text=ptext,
            content_type=pctype, chunker_version=chunker_version, chunk_index=parent_idx,
        )
        chunks.append(ChunkResult(
            id=pid, chunk_type="PARENT", parent_id=None, hierarchy_path=ppath,
            page=ppage, content_type=pctype, text=ptext, token_count=ptokens,
            source_offsets_start=None, source_offsets_end=None,
        ))
        parent_idx += 1
        words = ptext.split()
        total = len(words)
        pos = 0
        while pos < total:
            cw = words[pos:pos + child_token_max]
            ctext = " ".join(cw)
            ctokens = token_counter(ctext)
            if ctokens < child_token_min and pos + child_token_max >= total and chunks and chunks[-1].chunk_type == "CHILD":
                merged = chunks[-1].text + " " + ctext
                chunks[-1] = ChunkResult(
                    id=chunks[-1].id, chunk_type="CHILD", parent_id=pid, hierarchy_path=ppath,
                    page=ppage, content_type=pctype, text=merged, token_count=token_counter(merged),
                    source_offsets_start=pos, source_offsets_end=pos + len(cw),
                )
                break
            cid = _deterministic_chunk_id(
                version=chunker_version, hierarchy_path=ppath, text=ctext,
                content_type=pctype, chunker_version=chunker_version, chunk_index=child_idx,
            )
            chunks.append(ChunkResult(
                id=cid, chunk_type="CHILD", parent_id=pid, hierarchy_path=ppath,
                page=ppage, content_type=pctype, text=ctext, token_count=ctokens,
                source_offsets_start=pos, source_offsets_end=pos + len(cw),
            ))
            child_idx += 1
            pos += child_token_max
        parent_buffer = []
        parent_tokens = 0

    for element in doc.elements:
        etoks = token_counter(element.text)
        boundary = _is_boundary(element)
        if boundary and parent_buffer:
            _flush_parent()
        if etoks > child_token_hard_max:
            if parent_buffer:
                _flush_parent()
            words = element.text.split()
            total = len(words)
            pos = 0
            overlap = max(1, child_token_max // 5)
            while pos < total:
                cw = words[pos:pos + child_token_max]
                ctext = " ".join(cw)
                cid = _deterministic_chunk_id(
                    version=chunker_version, hierarchy_path=element.hierarchy_path, text=ctext,
                    content_type=element.type, chunker_version=chunker_version, chunk_index=pos,
                )
                chunks.append(ChunkResult(
                    id=cid, chunk_type="CHILD", parent_id=None, hierarchy_path=element.hierarchy_path,
                    page=element.page, content_type=element.type, text=ctext,
                    token_count=token_counter(ctext), source_offsets_start=pos, source_offsets_end=pos + len(cw),
                ))
                pos += max(1, child_token_max - overlap)
        else:
            if parent_tokens + etoks > parent_token_max and parent_buffer:
                _flush_parent()
            parent_buffer.append(element)
            parent_tokens += etoks
            if boundary and parent_buffer:
                _flush_parent()

    if parent_buffer:
        _flush_parent()
    return ChunkManifest(chunks=chunks)
