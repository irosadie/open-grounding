"""Mapping from docling's DoclingDocument to canonical DocumentElement records.

Separated from the adapter so the mapping logic can be unit-tested with mock
docling objects without the heavy ML dependency installed. The functions here
accept duck-typed objects matching docling's item shape (``label``, ``text``,
``prov`` with ``page_no`` and ``bbox``, ``data`` with ``grid``).
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from app.domain.rag.elements import (
    BoundingBox,
    DocumentElement,
    ElementType,
    ParsedDocument,
    ParserQualitySummary,
)

_DOCLING_LABEL_MAP: dict[str, str] = {
    "title": ElementType.TITLE,
    "section_header": ElementType.TITLE,
    "paragraph": ElementType.NARRATIVE,
    "text": ElementType.NARRATIVE,
    "narrative_text": ElementType.NARRATIVE,
    "list_item": ElementType.LIST,
    "list": ElementType.LIST,
    "table": ElementType.TABLE,
    "figure": ElementType.IMAGE,
    "picture": ElementType.IMAGE,
    "code": ElementType.CODE,
    "code_text": ElementType.CODE,
    "formula": ElementType.FORMULA,
    "caption": ElementType.NARRATIVE,
    "page_header": ElementType.NARRATIVE,
    "page_footer": ElementType.NARRATIVE,
    "footnote": ElementType.NARRATIVE,
}


class _DoclingItem(Protocol):
    label: str
    text: str

    @property
    def prov(self) -> list[object]: ...


def map_label(label: str) -> str:
    """Map a docling item label to a canonical element type."""
    normalized = label.lower().replace("-", "_").replace(" ", "_")
    return _DOCLING_LABEL_MAP.get(normalized, ElementType.NARRATIVE)


def extract_page(item: object) -> int | None:
    """Extract the page number from a docling item's provenance."""
    try:
        provs = getattr(item, "prov", []) or []
        if provs:
            first = provs[0]
            page = getattr(first, "page_no", None) or getattr(first, "page", None)
            return int(page) if page is not None else None
    except (IndexError, AttributeError, TypeError, ValueError):
        pass
    return None


def extract_bbox(item: object) -> BoundingBox | None:
    """Extract the bounding box from a docling item's provenance."""
    try:
        provs = getattr(item, "prov", []) or []
        if provs:
            first = provs[0]
            bbox = getattr(first, "bbox", None)
            if bbox is not None:
                left = float(getattr(bbox, "l", getattr(bbox, "left", 0.0)))
                top = float(getattr(bbox, "t", getattr(bbox, "top", 0.0)))
                right = float(getattr(bbox, "r", getattr(bbox, "right", 0.0)))
                bottom = float(getattr(bbox, "b", getattr(bbox, "bottom", 0.0)))
                return BoundingBox(left=left, top=top, right=right, bottom=bottom)
    except (IndexError, AttributeError, TypeError, ValueError):
        pass
    return None


def extract_confidence(item: object) -> float | None:
    """Extract layout model confidence from a docling item."""
    try:
        provs = getattr(item, "prov", []) or []
        if provs:
            first = provs[0]
            conf = getattr(first, "confidence", None)
            return float(conf) if conf is not None else None
    except (IndexError, AttributeError, TypeError, ValueError):
        pass
    return None


def extract_table_grid(item: object) -> dict[str, object] | None:
    """Extract a table grid as structured payload if the item is a table."""
    try:
        data = getattr(item, "data", None)
        if data is not None and hasattr(data, "grid"):
            grid = data.grid
            return {"grid": [[getattr(cell, "text", str(cell)) for cell in row.cells] for row in grid]}
    except (AttributeError, TypeError):
        pass
    return None


def deterministic_element_id(*, version: str, element_index: int, text: str, page: int | None) -> str:
    """Compute a deterministic element ID from version, index, text, and page."""
    raw = f"{version}:{element_index}:{page}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def map_docling_to_elements(doc: object, *, profile_version: str) -> ParsedDocument:
    """Map a duck-typed docling document to canonical elements + quality summary.

    Accepts any object with ``texts`` and ``tables`` attributes whose items
    expose ``label``, ``text``, ``prov``, and optionally ``data``. This makes
    the mapping testable with mock objects without docling installed.
    """
    texts: list[object] = list(getattr(doc, "texts", []) or [])
    tables: list[object] = list(getattr(doc, "tables", []) or [])
    all_items: list[object] = [*texts, *tables]

    def _order_key(item: object) -> tuple[int, int]:
        page = extract_page(item) or 0
        prov_index = 0
        try:
            provs = getattr(item, "prov", []) or []
            if provs:
                prov_index = int(getattr(provs[0], "index", 0))
        except (IndexError, AttributeError, TypeError, ValueError):
            pass
        return (page, prov_index)

    all_items.sort(key=_order_key)

    elements: list[DocumentElement] = []
    headings: list[str] = []
    pages_seen: set[int] = set()

    for idx, item in enumerate(all_items):
        label = getattr(item, "label", "paragraph")
        canonical_type = map_label(label)
        text = getattr(item, "text", "") or ""
        page = extract_page(item)
        if page is not None:
            pages_seen.add(page)
        if canonical_type == ElementType.TITLE and text:
            headings.append(text)
        element_id = deterministic_element_id(
            version=profile_version, element_index=idx, text=text, page=page
        )
        elements.append(
            DocumentElement(
                id=element_id,
                type=canonical_type,
                text=text,
                page=page,
                bounding_box=extract_bbox(item),
                hierarchy_path=tuple(headings),
                source_offsets=None,
                structured_payload=extract_table_grid(item),
                extraction_confidence=extract_confidence(item),
            )
        )

    total = len(elements)
    non_empty = sum(1 for e in elements if e.text.strip())
    text_coverage = non_empty / total if total else 0.0
    empty_ratio = 1.0 - text_coverage
    confs = [e.extraction_confidence for e in elements if e.extraction_confidence is not None]
    aggregate_conf = sum(confs) / len(confs) if confs else None
    page_coverage = len(pages_seen) / max(pages_seen) if pages_seen else None
    quality = ParserQualitySummary(
        element_count=total,
        text_coverage=text_coverage,
        empty_element_ratio=empty_ratio,
        page_coverage=page_coverage,
        aggregate_confidence=aggregate_conf,
    )
    return ParsedDocument(elements=elements, quality=quality)
