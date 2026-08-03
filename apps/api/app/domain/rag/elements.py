"""Canonical document element and parser-profile value objects.

These are the domain value objects produced by the ``DocumentParser`` port.
They match the canonical ``DocumentElement`` schema defined in the RAG
architecture: ordered elements with content type, text, page, bounding box,
hierarchy path, source offsets, structured payload, and extraction
confidence.

The parser adapter (e.g. docling) owns the translation from its native
output model to these value objects. Domain and application code never
import a parser SDK type — they consume ``DocumentElement`` records only.
"""

from dataclasses import dataclass, field


class ElementType:
    """Canonical element type enum (string constants, not StrEnum, to match
    the architecture spec's fixed vocabulary)."""

    TITLE = "title"
    NARRATIVE = "narrative"
    LIST = "list"
    TABLE = "table"
    IMAGE = "image"
    CODE = "code"
    FORMULA = "formula"


SUPPORTED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/markdown",
        "text/markdown",
        "text/plain",
        "text/x-markdown",
    }
)


@dataclass(frozen=True)
class BoundingBox:
    """Normalized or pixel bounding box for an element on a page."""

    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class SourceOffsets:
    """Source offsets locating an element within the raw source."""

    start: int
    end: int


@dataclass(frozen=True)
class DocumentElement:
    """An ordered canonical document element produced by a parser.

    Matches the architecture schema: ``id``, ``type``, ``text``, ``page``,
    ``bounding_box``, ``hierarchy_path``, ``source_offsets``,
    ``structured_payload``, ``extraction_confidence``.
    """

    id: str
    type: str
    text: str
    page: int | None = None
    bounding_box: BoundingBox | None = None
    hierarchy_path: tuple[str, ...] = field(default_factory=tuple)
    source_offsets: SourceOffsets | None = None
    structured_payload: dict[str, object] | None = None
    extraction_confidence: float | None = None


@dataclass(frozen=True)
class ParserQualitySummary:
    """Bounded parser-quality summary consumable by the quality gate.

    Low-confidence or insufficient extraction surfaces evidence here so the
    downstream quality gate can route to ``NEEDS_REVIEW`` or a bounded
    fallback without silently promoting empty content.
    """

    element_count: int
    text_coverage: float
    empty_element_ratio: float
    page_coverage: float | None
    aggregate_confidence: float | None


@dataclass(frozen=True)
class ParsedDocument:
    """Result of parsing a source: ordered elements plus a quality summary."""

    elements: list[DocumentElement]
    quality: ParserQualitySummary


@dataclass(frozen=True)
class ParserProfile:
    """Immutable, versioned parser-profile identity.

    Identifies the docling pipeline option, model, OCR toggle, and format
    options. A profile change creates a new generation rather than mutating
    parsed artifacts in place. Stores no secrets.
    """

    id: str
    pipeline: str
    model: str
    ocr_enabled: bool
    format_options: dict[str, object] = field(default_factory=dict)
    version: str = "1"
    is_active: bool = False
