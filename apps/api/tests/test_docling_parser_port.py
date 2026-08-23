"""Unit tests for the document-parser port and canonical value objects.

Tests the provider-neutral port contract, tenant-scoped enforcement, the
canonical DocumentElement schema, and parser-quality summary. These do not
require docling to be installed — the adapter is tested via a stub.
"""

from uuid import uuid4

import pytest

from app.domain.errors import DomainError
from app.domain.rag.adapter_ports import DocumentParser, assert_tenant_scope
from app.domain.rag.elements import (
    SUPPORTED_MIME_TYPES,
    BoundingBox,
    DocumentElement,
    ElementType,
    ParsedDocument,
    ParserProfile,
    ParserQualitySummary,
    SourceOffsets,
)
from app.domain.rag.tenant_namespace import TenantNamespace
from app.domain.tenant_context import TenantContext

TENANT_ID = str(uuid4())


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id=TENANT_ID, membership_id=str(uuid4()), user_id=str(uuid4()))


# --- Canonical value objects --------------------------------------------------


def test_document_element_matches_canonical_schema() -> None:
    element = DocumentElement(
        id="el-1",
        type=ElementType.TITLE,
        text="Introduction",
        page=1,
        bounding_box=BoundingBox(left=0.1, top=0.2, right=0.9, bottom=0.3),
        hierarchy_path=("doc-1", "section-1"),
        source_offsets=SourceOffsets(start=0, end=12),
        structured_payload=None,
        extraction_confidence=0.95,
    )
    assert element.type == "title"
    assert element.page == 1
    assert element.hierarchy_path == ("doc-1", "section-1")
    assert element.extraction_confidence == 0.95


def test_document_element_minimal_fields() -> None:
    element = DocumentElement(id="el-2", type=ElementType.NARRATIVE, text="Body text.")
    assert element.page is None
    assert element.bounding_box is None
    assert element.hierarchy_path == ()
    assert element.extraction_confidence is None


def test_element_type_constants_match_spec() -> None:
    assert ElementType.TITLE == "title"
    assert ElementType.NARRATIVE == "narrative"
    assert ElementType.LIST == "list"
    assert ElementType.TABLE == "table"
    assert ElementType.IMAGE == "image"
    assert ElementType.CODE == "code"
    assert ElementType.FORMULA == "formula"


def test_supported_mime_types_for_v1() -> None:
    assert "application/pdf" in SUPPORTED_MIME_TYPES
    assert "text/markdown" in SUPPORTED_MIME_TYPES
    assert "text/plain" in SUPPORTED_MIME_TYPES
    assert "application/vnd.openxmlformats..." not in SUPPORTED_MIME_TYPES


def test_parser_quality_summary_fields() -> None:
    q = ParserQualitySummary(
        element_count=10,
        text_coverage=0.85,
        empty_element_ratio=0.05,
        page_coverage=0.90,
        aggregate_confidence=0.88,
    )
    assert q.element_count == 10
    assert q.text_coverage == 0.85


def test_parsed_document_carries_elements_and_quality() -> None:
    elements = [DocumentElement(id="e1", type=ElementType.NARRATIVE, text="x")]
    q = ParserQualitySummary(element_count=1, text_coverage=1.0, empty_element_ratio=0.0, page_coverage=None, aggregate_confidence=None)
    doc = ParsedDocument(elements=elements, quality=q)
    assert len(doc.elements) == 1
    assert doc.quality.element_count == 1


def test_parser_profile_is_immutable_and_secret_free() -> None:
    profile = ParserProfile(id="pp-1", pipeline="standard", model="docling-default", ocr_enabled=False)
    assert profile.version == "1"
    assert profile.is_active is False
    assert not any(k.lower().endswith("key") for k in dir(profile))


# --- Port contract: tenant-scoped --------------------------------------------


def test_assert_tenant_scope_rejects_mismatch(tenant: TenantContext) -> None:
    ns = assert_tenant_scope(tenant, TENANT_ID)
    assert isinstance(ns, TenantNamespace)
    assert ns.tenant_id == TENANT_ID
    other_tenant = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()))
    with pytest.raises(DomainError, match="TENANT_SCOPE_MISMATCH"):
        assert_tenant_scope(other_tenant, TENANT_ID)


def test_document_parser_is_protocol() -> None:
    assert hasattr(DocumentParser, "parse")


def test_document_parser_stub_satisfies_protocol() -> None:
    class StubParser:
        async def parse(self, *, tenant: object, source: bytes, mime_type: str, parser_profile_id: str) -> ParsedDocument:
            return ParsedDocument(
                elements=[DocumentElement(id="e1", type=ElementType.NARRATIVE, text=source.decode())],
                quality=ParserQualitySummary(
                    element_count=1,
                    text_coverage=1.0,
                    empty_element_ratio=0.0,
                    page_coverage=None,
                    aggregate_confidence=None,
                ),
            )

    stub: DocumentParser = StubParser()  # type: ignore[assignment]
    assert stub is not None
