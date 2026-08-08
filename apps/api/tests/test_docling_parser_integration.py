"""Unit tests for docling parser integration in the parse stage.

Covers:
- _DEFAULT_PARSER_PROFILE fields
- _serialize_parsed_document() helper
- DoclingParserAdapter called when docling is available
- Graceful fallback to pdfminer when PARSER_NOT_INSTALLED
- Non-PARSER_NOT_INSTALLED DomainError propagates
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.stages.parse import (
    _DEFAULT_PARSER_PROFILE,
    _parse_with_docling_or_fallback,
    _serialize_parsed_document,
)


# ---------------------------------------------------------------------------
# 3.4 — _DEFAULT_PARSER_PROFILE fields
# ---------------------------------------------------------------------------


def test_default_parser_profile_fields() -> None:
    assert _DEFAULT_PARSER_PROFILE.id == "default-v1"
    assert _DEFAULT_PARSER_PROFILE.pipeline == "standard"
    assert _DEFAULT_PARSER_PROFILE.model == "layout"
    assert _DEFAULT_PARSER_PROFILE.ocr_enabled is False
    assert _DEFAULT_PARSER_PROFILE.version == "1"


# ---------------------------------------------------------------------------
# 3.3 — _serialize_parsed_document()
# ---------------------------------------------------------------------------


def _make_element(text: str) -> object:
    el = MagicMock()
    el.text = text
    return el


def test_serialize_joins_non_empty_elements() -> None:
    from app.domain.rag.elements import DocumentElement, ParsedDocument, ParserQualitySummary

    elements = [
        DocumentElement(id="1", type="narrative", text="First paragraph"),
        DocumentElement(id="2", type="narrative", text="Second paragraph"),
    ]
    quality = ParserQualitySummary(
        element_count=2, text_coverage=1.0, empty_element_ratio=0.0,
        page_coverage=None, aggregate_confidence=None,
    )
    doc = ParsedDocument(elements=elements, quality=quality)
    result = _serialize_parsed_document(doc)
    assert result == "First paragraph\nSecond paragraph"


def test_serialize_skips_whitespace_only_elements() -> None:
    from app.domain.rag.elements import DocumentElement, ParsedDocument, ParserQualitySummary

    elements = [
        DocumentElement(id="1", type="narrative", text="Real text"),
        DocumentElement(id="2", type="narrative", text="   "),
        DocumentElement(id="3", type="narrative", text="\n"),
        DocumentElement(id="4", type="narrative", text="More text"),
    ]
    quality = ParserQualitySummary(
        element_count=4, text_coverage=0.5, empty_element_ratio=0.5,
        page_coverage=None, aggregate_confidence=None,
    )
    doc = ParsedDocument(elements=elements, quality=quality)
    result = _serialize_parsed_document(doc)
    assert result == "Real text\nMore text"


def test_serialize_returns_empty_string_when_all_empty() -> None:
    from app.domain.rag.elements import DocumentElement, ParsedDocument, ParserQualitySummary

    elements = [
        DocumentElement(id="1", type="narrative", text="   "),
        DocumentElement(id="2", type="narrative", text=""),
    ]
    quality = ParserQualitySummary(
        element_count=2, text_coverage=0.0, empty_element_ratio=1.0,
        page_coverage=None, aggregate_confidence=None,
    )
    doc = ParsedDocument(elements=elements, quality=quality)
    result = _serialize_parsed_document(doc)
    assert result == ""


# ---------------------------------------------------------------------------
# 3.1 — docling installed path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_with_docling_calls_adapter_and_returns_text() -> None:
    from app.domain.rag.elements import DocumentElement, ParsedDocument, ParserQualitySummary

    elements = [DocumentElement(id="1", type="narrative", text="Docling extracted text")]
    quality = ParserQualitySummary(
        element_count=1, text_coverage=1.0, empty_element_ratio=0.0,
        page_coverage=None, aggregate_confidence=None,
    )
    parsed_doc = ParsedDocument(elements=elements, quality=quality)

    mock_adapter = MagicMock()
    mock_adapter.parse = AsyncMock(return_value=parsed_doc)

    with patch("app.workers.stages.parse.DoclingParserAdapter", return_value=mock_adapter):
        result = await _parse_with_docling_or_fallback(
            raw_content=b"pdf bytes",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="tenant-1",
        )

    assert result == parsed_doc
    mock_adapter.parse.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3.2 — PARSER_NOT_INSTALLED fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_falls_back_to_pdfminer_on_not_installed() -> None:
    from app.domain.errors import DomainError

    mock_adapter = MagicMock()
    mock_adapter.parse = AsyncMock(
        side_effect=DomainError("PARSER_NOT_INSTALLED", "docling not installed", 500)
    )

    with (
        patch("app.workers.stages.parse.DoclingParserAdapter", return_value=mock_adapter),
        patch("app.workers.stages.parse._extract_text", return_value="pdfminer text") as mock_extract,
    ):
        result = await _parse_with_docling_or_fallback(
            raw_content=b"pdf bytes",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="tenant-1",
        )

    assert result == "pdfminer text"
    mock_extract.assert_called_once()


@pytest.mark.asyncio
async def test_parse_falls_back_on_import_error() -> None:
    with (
        patch("app.workers.stages.parse.DoclingParserAdapter", side_effect=ImportError("no module")),
        patch("app.workers.stages.parse._extract_text", return_value="fallback text") as mock_extract,
    ):
        result = await _parse_with_docling_or_fallback(
            raw_content=b"bytes",
            mime_type="text/plain",
            filename="doc.txt",
            tenant_id="tenant-1",
        )

    assert result == "fallback text"
    mock_extract.assert_called_once()


# ---------------------------------------------------------------------------
# 3.5 — Non-PARSER_NOT_INSTALLED DomainError propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_propagates_non_parser_domain_error() -> None:
    from app.domain.errors import DomainError

    mock_adapter = MagicMock()
    mock_adapter.parse = AsyncMock(
        side_effect=DomainError("UNSUPPORTED_MIME_TYPE", "unsupported", 400)
    )

    with patch("app.workers.stages.parse.DoclingParserAdapter", return_value=mock_adapter):
        with pytest.raises(DomainError) as exc_info:
            await _parse_with_docling_or_fallback(
                raw_content=b"bytes",
                mime_type="application/unknown",
                filename="file.bin",
                tenant_id="tenant-1",
            )

    assert exc_info.value.code == "UNSUPPORTED_MIME_TYPE"
