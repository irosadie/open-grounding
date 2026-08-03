## 1. Parser port and canonical value objects

- [x] 1.1 Verify `rag-platform-foundation` provider ports and tenant context are available to the RAG domain modules.
- [x] 1.2 Add the `DocumentParser` provider `Protocol` to `app/domain/rag/adapter_ports.py`, requiring `TenantContext` and a source reference and returning ordered `DocumentElement` records without exposing any parser SDK type.
- [x] 1.3 Add the `DocumentElement` and `ParserProfile` domain value objects matching the canonical schema (`id`, `type`, `text`, `page`, `bounding_box`, `hierarchy_path`, `source_offsets`, `structured_payload`, `extraction_confidence`) and the parser-profile identity fields.
- [x] 1.4 Add unit tests proving the port is tenant-scoped, returns canonical value objects, and rejects missing or mismatched tenant context.

## 2. Docling dependency and adapter implementation

- [x] 2.1 Add `docling` (and its layout-model dependency) to the API/worker Python dependency set with pinned docling and model versions, and to the ingestion worker runtime profile; keep existing FastAPI, PostgreSQL, Redis, and Node worker behavior unchanged.
- [x] 2.2 Implement the `DoclingParserAdapter` in `app/infrastructure/rag/parsers/` behind the `DocumentParser` port, importing docling only in infrastructure and never in domain or application code.
- [x] 2.3 Implement the `DoclingDocument` → `DocumentElement` mapping preserving reading order, page number, bounding box, hierarchy path, source offsets, structured payload (table grids), and extraction confidence per element.
- [x] 2.4 Derive `hierarchy_path` from the docling heading tree and map docling item labels to the canonical type enum (`title | narrative | list | table | image | code | formula`).
- [x] 2.5 Emit a bounded parser-quality summary (text coverage, empty-element ratio, page coverage for PDF, and aggregate confidence) consumable by the downstream normalization and quality gate.

## 3. Parser-profile configuration and reproducibility

- [x] 3.1 Add Pydantic parser-profile configuration (docling pipeline option, model identifier, OCR toggle, format options) with validation and no stored secrets.
- [x] 3.2 Persist an immutable, versioned parser profile referenced by the ingestion pipeline fingerprint; ensure a profile change creates a new generation rather than mutating parsed artifacts in place.
- [x] 3.3 Implement deterministic element identifiers and output for the same source bytes plus the same parser profile, with tests proving identical reruns produce identical element manifests without duplicates.

## 4. Regression fixtures and tests

- [x] 4.1 Add parser regression fixtures for digital PDF (page lineage and reading order), Markdown (heading and code-block boundaries), and TXT (narrative elements).
- [x] 4.2 Add contract and regression tests proving PDF elements retain page and bounding box, Markdown preserves heading hierarchy and code blocks, and TXT becomes ordered narrative elements.
- [x] 4.3 Add tests proving low-confidence or low-coverage extraction surfaces quality signals without silently producing ready output, and that the adapter does not expose docling SDK types beyond infrastructure.

## 5. Documentation, architecture alignment, and verification

- [x] 5.1 Update `docs/RAG-ARCHITECTURE.md` §18 references from Unstructured to docling and record docling as the first supported parser in the parser-routing section.
- [x] 5.2 Close the `rag-ingestion-foundation` open question "Which parser adapter is officially supported first for digital PDFs" by pointing to this change.
- [x] 5.3 Document parser-profile options, supported formats, deferred formats (OCR, office, HTML, email), worker runtime requirements, and the handoff to `rag-ingestion-foundation` task 3.1.
- [x] 5.4 Export generated FastAPI OpenAPI where applicable and run FastAPI lint, type, unit, and parser-fixture checks plus the documented full repository quality gate.
