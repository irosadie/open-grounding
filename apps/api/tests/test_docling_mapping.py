"""Tests for the docling -> canonical element mapping and adapter contract.

Uses mock docling objects (duck-typed) so the mapping logic is tested without
the heavy ML dependency installed.
"""

from uuid import uuid4

import pytest

from app.domain.errors import DomainError
from app.domain.rag.elements import ElementType, ParserProfile
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag.parsers.mapping import map_docling_to_elements, map_label


class _MockBBox:
    def __init__(self, left_v: float, top_v: float, right_v: float, bottom_v: float) -> None:
        self.l = left_v
        self.t = top_v
        self.r = right_v
        self.b = bottom_v


class _MockProv:
    def __init__(self, page_no: int, bbox: _MockBBox, confidence: float = 0.9, index: int = 0) -> None:
        self.page_no = page_no
        self.bbox = bbox
        self.confidence = confidence
        self.index = index


class _MockItem:
    def __init__(self, label: str, text: str, page: int = 1, conf: float = 0.9, index: int = 0) -> None:
        self.label = label
        self.text = text
        self.prov = [_MockProv(page, _MockBBox(0.1, 0.2, 0.9, 0.3), conf, index)]


class _MockTableCell:
    def __init__(self, text: str) -> None:
        self.text = text


class _MockTableRow:
    def __init__(self, cells: list[_MockTableCell]) -> None:
        self.cells = cells


class _MockTableData:
    def __init__(self, rows: list[_MockTableRow]) -> None:
        self.grid = rows  # docling's grid is a list of TableRow objects


class _MockTableItem:
    def __init__(self, label: str, text: str, page: int, grid_rows: list[list[str]]) -> None:
        self.label = label
        self.text = text
        self.prov = [_MockProv(page, _MockBBox(0.1, 0.2, 0.9, 0.5), 0.8, 0)]
        row_objs = [_MockTableRow([_MockTableCell(c) for c in row]) for row in grid_rows]
        self.data = _MockTableData(row_objs)


class _MockDoclingDocument:
    def __init__(self, texts: list[_MockItem], tables: list[_MockTableItem] | None = None) -> None:
        self.texts = texts
        self.tables = tables or []


TENANT_ID = str(uuid4())


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id=TENANT_ID, membership_id=str(uuid4()), user_id=str(uuid4()))


@pytest.fixture
def profile() -> ParserProfile:
    return ParserProfile(id="pp-1", pipeline="standard", model="docling-default", ocr_enabled=False)


def test_label_map_covers_canonical_types() -> None:
    assert map_label("title") == ElementType.TITLE
    assert map_label("paragraph") == ElementType.NARRATIVE
    assert map_label("list_item") == ElementType.LIST
    assert map_label("table") == ElementType.TABLE
    assert map_label("figure") == ElementType.IMAGE
    assert map_label("code") == ElementType.CODE
    assert map_label("formula") == ElementType.FORMULA


def test_label_map_defaults_unknown_to_narrative() -> None:
    assert map_label("unknown_label") == ElementType.NARRATIVE


def test_mapping_preserves_page_and_bbox() -> None:
    doc = _MockDoclingDocument([_MockItem("paragraph", "Hello", page=3)])
    result = map_docling_to_elements(doc, profile_version="1")
    assert len(result.elements) == 1
    el = result.elements[0]
    assert el.page == 3
    assert el.bounding_box is not None
    assert el.bounding_box.left == 0.1


def test_mapping_derives_hierarchy_from_titles() -> None:
    doc = _MockDoclingDocument([
        _MockItem("title", "Chapter 1", page=1),
        _MockItem("paragraph", "Body", page=1),
        _MockItem("title", "Section 1.1", page=1),
        _MockItem("paragraph", "More body", page=2),
    ])
    result = map_docling_to_elements(doc, profile_version="1")
    assert result.elements[1].hierarchy_path == ("Chapter 1",)
    assert result.elements[3].hierarchy_path == ("Chapter 1", "Section 1.1")


def test_mapping_preserves_reading_order() -> None:
    doc = _MockDoclingDocument([
        _MockItem("paragraph", "page2", page=2, index=0),
        _MockItem("paragraph", "page1", page=1, index=0),
    ])
    result = map_docling_to_elements(doc, profile_version="1")
    assert result.elements[0].page == 1
    assert result.elements[1].page == 2


def test_mapping_extracts_table_grid() -> None:
    table = _MockTableItem("table", "A table", page=1, grid_rows=[["a", "b"], ["c", "d"]])
    doc = _MockDoclingDocument([], [table])
    result = map_docling_to_elements(doc, profile_version="1")
    el = result.elements[0]
    assert el.type == ElementType.TABLE
    assert el.structured_payload is not None
    assert el.structured_payload["grid"] == [["a", "b"], ["c", "d"]]


def test_deterministic_ids_are_stable() -> None:
    doc = _MockDoclingDocument([_MockItem("paragraph", "Same text", page=1)])
    r1 = map_docling_to_elements(doc, profile_version="1")
    r2 = map_docling_to_elements(doc, profile_version="1")
    assert r1.elements[0].id == r2.elements[0].id


def test_deterministic_ids_change_with_profile_version() -> None:
    doc = _MockDoclingDocument([_MockItem("paragraph", "Same text", page=1)])
    r1 = map_docling_to_elements(doc, profile_version="1")
    r2 = map_docling_to_elements(doc, profile_version="2")
    assert r1.elements[0].id != r2.elements[0].id


def test_quality_summary_reports_coverage() -> None:
    doc = _MockDoclingDocument([_MockItem("paragraph", "text", conf=0.9), _MockItem("paragraph", "", conf=0.5)])
    result = map_docling_to_elements(doc, profile_version="1")
    assert result.quality.element_count == 2
    assert result.quality.text_coverage == 0.5
    assert result.quality.empty_element_ratio == 0.5
    assert result.quality.aggregate_confidence is not None


def test_empty_document_produces_zero_quality() -> None:
    doc = _MockDoclingDocument([])
    result = map_docling_to_elements(doc, profile_version="1")
    assert result.quality.element_count == 0
    assert result.quality.text_coverage == 0.0


async def test_adapter_rejects_unsupported_mime(tenant: TenantContext, profile: ParserProfile) -> None:
    from app.infrastructure.rag.parsers.docling_adapter import DoclingParserAdapter

    adapter = DoclingParserAdapter(expected_tenant_id=TENANT_ID, profile=profile)
    with pytest.raises(DomainError, match="UNSUPPORTED_MIME_TYPE"):
        await adapter.parse(tenant=tenant, source=b"...", mime_type="application/vnd.ms-excel", parser_profile_id="pp-1")


async def test_adapter_rejects_profile_mismatch(tenant: TenantContext, profile: ParserProfile) -> None:
    from app.infrastructure.rag.parsers.docling_adapter import DoclingParserAdapter

    adapter = DoclingParserAdapter(expected_tenant_id=TENANT_ID, profile=profile)
    with pytest.raises(DomainError, match="PARSER_PROFILE_MISMATCH"):
        await adapter.parse(tenant=tenant, source=b"...", mime_type="text/plain", parser_profile_id="wrong")


async def test_adapter_rejects_tenant_mismatch(profile: ParserProfile) -> None:
    from app.infrastructure.rag.parsers.docling_adapter import DoclingParserAdapter

    other = TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()))
    adapter = DoclingParserAdapter(expected_tenant_id=TENANT_ID, profile=profile)
    with pytest.raises(DomainError, match="TENANT_SCOPE_MISMATCH"):
        await adapter.parse(tenant=other, source=b"...", mime_type="text/plain", parser_profile_id="pp-1")


def test_adapter_module_imports_without_docling() -> None:
    import importlib

    mod = importlib.import_module("app.infrastructure.rag.parsers.docling_adapter")
    assert hasattr(mod, "DoclingParserAdapter")
