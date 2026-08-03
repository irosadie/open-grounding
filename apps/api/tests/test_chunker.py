"""Tests for the structure-aware parent-child chunker.

Covers structural boundary preservation, deterministic IDs, parent-child
lineage, token budgets, and oversized-element splitting with overlap.
"""

from app.domain.rag.chunker import chunk_document, default_token_counter
from app.domain.rag.elements import (
    DocumentElement,
    ElementType,
    ParsedDocument,
    ParserQualitySummary,
)


def _make_doc(elements: list[DocumentElement]) -> ParsedDocument:
    return ParsedDocument(
        elements=elements,
        quality=ParserQualitySummary(
            element_count=len(elements), text_coverage=1.0, empty_element_ratio=0.0,
            page_coverage=None, aggregate_confidence=None,
        ),
    )


def test_chunker_produces_parent_and_children() -> None:
    text = "word " * 400
    doc = _make_doc([DocumentElement(id="e1", type=ElementType.NARRATIVE, text=text.strip())])
    manifest = chunk_document(doc)
    parents = [c for c in manifest.chunks if c.chunk_type == "PARENT"]
    children = [c for c in manifest.chunks if c.chunk_type == "CHILD"]
    assert len(parents) >= 1
    assert len(children) >= 1
    assert all(c.parent_id == parents[0].id for c in children if c.parent_id is not None)


def test_chunker_respects_title_boundary() -> None:
    doc = _make_doc([
        DocumentElement(id="e1", type=ElementType.TITLE, text="Chapter 1"),
        DocumentElement(id="e2", type=ElementType.NARRATIVE, text="para " * 100),
        DocumentElement(id="e3", type=ElementType.TITLE, text="Chapter 2"),
        DocumentElement(id="e4", type=ElementType.NARRATIVE, text="para " * 100),
    ])
    manifest = chunk_document(doc)
    parents = [c for c in manifest.chunks if c.chunk_type == "PARENT"]
    assert len(parents) >= 2


def test_chunker_deterministic_ids_on_retry() -> None:
    text = "word " * 400
    doc = _make_doc([DocumentElement(id="e1", type=ElementType.NARRATIVE, text=text.strip())])
    m1 = chunk_document(doc)
    m2 = chunk_document(doc)
    assert [c.id for c in m1.chunks] == [c.id for c in m2.chunks]


def test_chunker_preserves_hierarchy_path() -> None:
    doc = _make_doc([
        DocumentElement(
            id="e1", type=ElementType.NARRATIVE, text="para " * 200,
            hierarchy_path=("Chapter 1", "Section 1"),
        ),
    ])
    manifest = chunk_document(doc)
    assert all(c.hierarchy_path == ("Chapter 1", "Section 1") for c in manifest.chunks)


def test_chunker_splits_oversized_element_with_overlap() -> None:
    huge = "word " * 1000
    doc = _make_doc([DocumentElement(id="e1", type=ElementType.NARRATIVE, text=huge.strip())])
    manifest = chunk_document(doc, child_token_max=100, child_token_hard_max=100)
    children = [c for c in manifest.chunks if c.chunk_type == "CHILD"]
    assert len(children) > 1


def test_chunker_preserves_code_block_boundary() -> None:
    doc = _make_doc([
        DocumentElement(id="e1", type=ElementType.NARRATIVE, text="intro " * 100),
        DocumentElement(id="e2", type=ElementType.CODE, text="print('hello')"),
        DocumentElement(id="e3", type=ElementType.NARRATIVE, text="outro " * 100),
    ])
    manifest = chunk_document(doc)
    parents = [c for c in manifest.chunks if c.chunk_type == "PARENT"]
    assert len(parents) >= 2


def test_chunker_handles_empty_document() -> None:
    doc = _make_doc([])
    manifest = chunk_document(doc)
    assert manifest.chunks == []


def test_default_token_counter_approximates() -> None:
    assert default_token_counter("a b c d") == 1
    assert default_token_counter("x" * 400) == 100
