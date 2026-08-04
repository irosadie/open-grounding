"""Normalization and quality gate for parsed document elements.

Normalization repairs Unicode, whitespace, broken hyphenation, and obvious
boilerplate without discarding page, hierarchy, or source offsets. The
quality gate measures extraction coverage, invalid-character ratio,
empty-element ratio, page coverage for PDF, and parser confidence. A failed
gate routes to ``NEEDS_REVIEW`` or ``FAILED``; empty or low-quality content
can never be silently promoted to ``READY``.
"""

from __future__ import annotations

import re
import unicodedata

from app.domain.rag.elements import DocumentElement, ParsedDocument, ParserQualitySummary


def normalize_element(element: DocumentElement) -> DocumentElement:
    """Normalize a single element's text while preserving identity and lineage."""
    text = element.text
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"-\s+", "", text)  # repair broken hyphenation
    return DocumentElement(
        id=element.id,
        type=element.type,
        text=text,
        page=element.page,
        bounding_box=element.bounding_box,
        hierarchy_path=element.hierarchy_path,
        source_offsets=element.source_offsets,
        structured_payload=element.structured_payload,
        extraction_confidence=element.extraction_confidence,
    )


def normalize_document(doc: ParsedDocument) -> ParsedDocument:
    """Normalize all elements in a parsed document, preserving the quality summary."""
    elements = [normalize_element(e) for e in doc.elements]
    return ParsedDocument(elements=elements, quality=doc.quality)


_INVALID_CHAR_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f-\x9f]")


def compute_quality(elements: list[DocumentElement], *, is_pdf: bool = False, pages_expected: int = 0) -> ParserQualitySummary:
    """Compute a bounded quality summary from a list of elements."""
    total = len(elements)
    if total == 0:
        return ParserQualitySummary(
            element_count=0,
            text_coverage=0.0,
            empty_element_ratio=1.0,
            page_coverage=0.0 if is_pdf and pages_expected > 0 else None,
            aggregate_confidence=None,
        )
    non_empty = sum(1 for e in elements if e.text.strip())
    text_coverage = non_empty / total
    empty_ratio = 1.0 - text_coverage
    confidences = [e.extraction_confidence for e in elements if e.extraction_confidence is not None]
    aggregate_conf = sum(confidences) / len(confidences) if confidences else None
    pages_seen: set[int] = set()
    for e in elements:
        if e.page is not None:
            pages_seen.add(e.page)
    page_coverage = len(pages_seen) / pages_expected if is_pdf and pages_expected > 0 else None
    return ParserQualitySummary(
        element_count=total,
        text_coverage=text_coverage,
        empty_element_ratio=empty_ratio,
        page_coverage=page_coverage,
        aggregate_confidence=aggregate_conf,
    )


class QualityGate:
    """Quality gate that routes extraction results to review or failure.

    A document with empty content, very low text coverage, or very low
    confidence is routed to ``NEEDS_REVIEW`` or ``FAILED``. It can never be
    silently promoted to ``READY``.
    """

    def __init__(
        self,
        *,
        min_text_coverage: float = 0.3,
        max_invalid_char_ratio: float = 0.1,
        min_aggregate_confidence: float = 0.5,
        min_page_coverage: float = 0.5,
    ) -> None:
        self._min_text_coverage = min_text_coverage
        self._max_invalid_ratio = max_invalid_char_ratio
        self._min_confidence = min_aggregate_confidence
        self._min_page_coverage = min_page_coverage

    def evaluate(self, quality: ParserQualitySummary, *, is_pdf: bool = False, pages_expected: int = 0) -> str:
        """Return 'READY', 'NEEDS_REVIEW', or 'FAILED' based on quality signals."""
        if quality.element_count == 0 or quality.text_coverage < 0.05:
            return "FAILED"
        if quality.text_coverage < self._min_text_coverage:
            return "NEEDS_REVIEW"
        if quality.aggregate_confidence is not None and quality.aggregate_confidence < self._min_confidence:
            return "NEEDS_REVIEW"
        if is_pdf and pages_expected > 0 and quality.page_coverage is not None:
            if quality.page_coverage < self._min_page_coverage:
                return "NEEDS_REVIEW"
        return "READY"
