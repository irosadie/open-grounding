# rag-docling-parser-adapter Specification

## Purpose
TBD - created by archiving change rag-docling-parser-adapter. Update Purpose after archive.
## Requirements
### Requirement: Document parsing is a tenant-aware provider port
The system SHALL define a `DocumentParser` provider port that requires a `TenantContext`
and a source reference and returns ordered canonical `DocumentElement` records. The port
MUST reject missing or mismatched tenant scope before any parser operation executes, and
domain or application code MUST NOT import a parser SDK type.

#### Scenario: Application service requests a parse
- **WHEN** an ingestion worker invokes the document-parser port for tenant-owned content
- **THEN** it supplies tenant context and a source reference and receives canonical
  document elements without importing a docling SDK type

### Requirement: Docling is the first officially supported parser adapter
The system SHALL provide a docling-backed `DocumentParser` adapter as the first
officially supported parser for digital PDF, Markdown, and plain-text sources. The
adapter MUST be selected through parser-profile configuration and MUST NOT be hard-coded
in domain or application code.

#### Scenario: Digital PDF is parsed
- **WHEN** a supported digital PDF enters the parsing stage
- **THEN** the docling adapter produces ordered page-aware canonical elements that later
  chunking can consume without parsing the raw PDF again

### Requirement: Parser output maps to canonical document elements
The docling adapter SHALL map `DoclingDocument` items to `DocumentElement` records that
retain `id`, `type`, `text`, `page`, `bounding_box`, `hierarchy_path`,
`source_offsets`, `structured_payload`, and `extraction_confidence`. Table elements
MUST carry their grid in `structured_payload`, and every element MUST carry a
non-null `extraction_confidence` when the parser provides one.

#### Scenario: PDF page and structure are preserved
- **WHEN** a digital PDF with headings, paragraphs, a list, and a table is parsed
- **THEN** the resulting elements retain page numbers, bounding boxes, heading
  hierarchy, list ordering, and the table grid as structured payload

### Requirement: Reading order and hierarchy are preserved
The adapter SHALL preserve docling reading order and derive `hierarchy_path` from the
document heading tree so chunking and citation can use section lineage. Markdown
headings and code blocks MUST be retained as structural boundaries, and plain text MUST
become ordered narrative elements.

#### Scenario: Markdown heading and code block are retained
- **WHEN** a Markdown source with a heading and a code block is parsed
- **THEN** the heading hierarchy and code-block boundary are retained in the resulting
  canonical elements

### Requirement: Parsing is deterministic and profile-versioned
The system SHALL persist an immutable, versioned parser profile identifying the docling
pipeline, model, and options. The same source bytes plus the same parser profile MUST
produce identical canonical elements and element identifiers on retry, and a profile
change MUST create a new generation rather than mutating parsed artifacts in place.

#### Scenario: Pipeline retries parsing
- **WHEN** the same source version and parser profile are processed again
- **THEN** the adapter produces the same element identities and content without creating
  duplicate parser artifacts

### Requirement: Parser quality signals are exposed
The adapter SHALL emit per-element `extraction_confidence` and a bounded parser-quality
summary including text coverage, empty-element ratio, page coverage for PDF, and
aggregate confidence. Low-confidence or insufficient extraction MUST surface quality
evidence so the downstream quality gate can route it to `NEEDS_REVIEW` or a bounded
fallback without silently promoting empty or low-quality content to ready.

#### Scenario: Extraction has insufficient coverage
- **WHEN** a parsed PDF fails configured text or page-coverage thresholds
- **THEN** the adapter quality summary reports the failure evidence so indexing is
  blocked by the downstream quality gate

### Requirement: Parsing runs in the worker, not the request path
The `DocumentParser` port MUST be invoked only by the ingestion worker stage. The FastAPI
application MAY validate and select parser profiles, but it MUST NOT execute docling
conversion synchronously in an HTTP request path. The worker MUST reject any job whose
tenant scope is missing or does not match the deployment tenant.

#### Scenario: HTTP request does not invoke the parser
- **WHEN** a caller creates or checks an ingestion through FastAPI
- **THEN** no docling conversion runs synchronously in that request; parsing is
  dispatched to the ingestion worker under tenant scope

### Requirement: Parser scope is limited to officially supported formats
The docling adapter SHALL officially support digital PDF, Markdown, and plain text for
v1. Scanned-PDF OCR, DOCX, PPTX, XLSX, HTML, email, images, chart understanding, and
code-AST parsing MUST be explicitly deferred to a later format-extension change, even
where docling supports them, to match the ingestion MVP scope.

#### Scenario: An unsupported format is requested
- **WHEN** a source with an unsupported MIME type is routed to the parser
- **THEN** the adapter rejects it as unsupported for v1 without attempting conversion

