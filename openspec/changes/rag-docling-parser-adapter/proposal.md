## Why

The RAG architecture requires every parser to emit ordered canonical `DocumentElement`
records (id, type, text, page, bounding_box, hierarchy_path, source_offsets,
structured_payload, extraction_confidence), and the ingestion foundation leaves the
choice of the first supported parser as an explicit open question. Selecting a concrete
parser adapter now unblocks ingestion task 3.1, removes ambiguity for implementers, and
keeps the decision inside the provider-neutral port model instead of leaking a parser
SDK into the domain.

## What Changes

- Add a tenant-aware `DocumentParser` provider port to the RAG domain, parallel to the
  existing object-store, queue, and vector ports, so domain and application code never
  import a parser SDK type.
- Add a docling-backed `DocumentParser` adapter as the first officially supported
  parser for digital PDF, Markdown, and plain-text sources, mapping `DoclingDocument`
  items to canonical `DocumentElement` records.
- Preserve page numbers, bounding boxes, reading order, heading hierarchy, source
  offsets, table grids, and extraction confidence so downstream chunking, citation, and
  quality gates can run without re-parsing the raw source.
- Add an immutable, versioned parser profile (docling pipeline, model, options) and
  deterministic element identifiers so retries and reindex are reproducible.
- Add parser regression fixtures and tests for digital PDF, Markdown, and TXT.
- Update `docs/RAG-ARCHITECTURE.md` references from Unstructured to docling and close
  the `rag-ingestion-foundation` open question on the first supported parser.
- Exclude scanned-PDF OCR, DOCX, PPTX, XLSX, HTML, email, images, chart understanding,
  code-AST parsing, the full ingestion pipeline, intake/versioning, chunking,
  embedding, indexing, and the frontend UI.

## Capabilities

### New Capabilities

- `rag-docling-parser-adapter`: Define the tenant-aware document-parser port and the
  docling-backed adapter that produces canonical, page-aware, hierarchy-preserving
  document elements for digital PDF, Markdown, and plain text.

### Modified Capabilities

None. No main OpenSpec capability specifications exist yet.

## Impact

- Adds FastAPI domain value objects (`DocumentElement`, `ParserProfile`), a
  `DocumentParser` provider port in `app/domain/rag/adapter_ports.py`, and a docling
  infrastructure adapter in `app/infrastructure/rag/parsers/` with its mapping and tests.
- Adds `docling` and its layout-model dependency to the API/worker Python dependency
  set and to the ingestion worker runtime profile; the FastAPI request path does not
  run docling conversion.
- Depends on `rag-platform-foundation` for the provider-port pattern, tenant context,
  and parser-profile configuration. It is consumed by `rag-ingestion-foundation`
  task 3.1 and closes that change's open question on the first supported parser.
- Updates architecture documentation and the ingestion foundation open question; it does
  not add catalog tables, migrations, intake routes, or a frontend ingestion UI.
