"""Tests for normalization, quality gate, and ingestion routes."""

from app.domain.rag.elements import DocumentElement, ElementType, ParsedDocument, ParserQualitySummary
from app.domain.rag.normalizer import QualityGate, compute_quality, normalize_element


def _doc(elements: list[DocumentElement]) -> ParsedDocument:
    q = compute_quality(elements)
    return ParsedDocument(elements=elements, quality=q)


def test_normalize_repairs_whitespace_and_hyphenation() -> None:
    el = DocumentElement(id="e1", type=ElementType.NARRATIVE, text="Hello  world-\n break")
    result = normalize_element(el)
    assert "  " not in result.text
    assert "\n" not in result.text
    assert "-\n" not in result.text


def test_normalize_preserves_page_and_hierarchy() -> None:
    el = DocumentElement(
        id="e1",
        type=ElementType.TITLE,
        text="Title",
        page=3,
        hierarchy_path=("Ch1",),
        extraction_confidence=0.9,
    )
    result = normalize_element(el)
    assert result.page == 3
    assert result.hierarchy_path == ("Ch1",)
    assert result.extraction_confidence == 0.9


def test_quality_gate_empty_returns_failed() -> None:
    q = ParserQualitySummary(element_count=0, text_coverage=0.0, empty_element_ratio=1.0, page_coverage=None, aggregate_confidence=None)
    gate = QualityGate()
    assert gate.evaluate(q) == "FAILED"


def test_quality_gate_low_coverage_returns_review() -> None:
    q = ParserQualitySummary(element_count=10, text_coverage=0.1, empty_element_ratio=0.9, page_coverage=None, aggregate_confidence=0.8)
    gate = QualityGate(min_text_coverage=0.3)
    assert gate.evaluate(q) == "NEEDS_REVIEW"


def test_quality_gate_low_confidence_returns_review() -> None:
    q = ParserQualitySummary(element_count=5, text_coverage=0.9, empty_element_ratio=0.1, page_coverage=None, aggregate_confidence=0.2)
    gate = QualityGate(min_aggregate_confidence=0.5)
    assert gate.evaluate(q) == "NEEDS_REVIEW"


def test_quality_gate_good_extraction_returns_ready() -> None:
    q = ParserQualitySummary(element_count=10, text_coverage=0.95, empty_element_ratio=0.05, page_coverage=None, aggregate_confidence=0.9)
    gate = QualityGate()
    assert gate.evaluate(q) == "READY"


def test_quality_gate_pdf_low_page_coverage_returns_review() -> None:
    q = ParserQualitySummary(element_count=10, text_coverage=0.9, empty_element_ratio=0.1, page_coverage=0.2, aggregate_confidence=0.9)
    gate = QualityGate(min_page_coverage=0.5)
    assert gate.evaluate(q, is_pdf=True, pages_expected=10) == "NEEDS_REVIEW"


def test_compute_quality_empty() -> None:
    q = compute_quality([])
    assert q.element_count == 0
    assert q.text_coverage == 0.0


def test_compute_quality_non_empty() -> None:
    elements = [
        DocumentElement(id="e1", type=ElementType.NARRATIVE, text="hello world"),
        DocumentElement(id="e2", type=ElementType.NARRATIVE, text="", extraction_confidence=0.8),
    ]
    q = compute_quality(elements)
    assert q.element_count == 2
    assert q.text_coverage == 0.5
    assert q.aggregate_confidence == 0.8
