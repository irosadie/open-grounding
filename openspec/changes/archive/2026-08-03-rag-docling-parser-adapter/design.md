## Context

`rag-platform-foundation` supplies the provider-port pattern, tenant context, and the
parser-profile configuration surface. `rag-ingestion-foundation` defines the canonical
`DocumentElement` schema, normalization, quality gates, chunking, and the staged
ingestion workflow, but leaves the first supported parser as an open question. This
change answers that question with a concrete, independently testable adapter: a
docling-backed `DocumentParser` behind the existing provider-port family.

The API remains FastAPI and the ingestion worker remains Node BullMQ plus internal
FastAPI commands. The parser adapter is invoked only by the ingestion worker stage;
the FastAPI request path may validate and select parser profiles but must not run
docling conversion synchronously. Domain and application code must not import docling.

Docling is chosen because its `DoclingDocument` output model maps nearly one-to-one to
the required canonical elements: typed items (`Title`, `Text`, `ListItem`,
`TableItem`, `Figure`, `CodeTextItem`, `FormulaItem`), per-item provenance with page
number and bounding box, reading order, heading hierarchy, table grids, and layout
confidence.

## Goals / Non-Goals

**Goals:**

- Add the `DocumentParser` provider port as a tenant-aware, provider-neutral contract.
- Add a docling adapter as the first officially supported parser for digital PDF,
  Markdown, and plain text.
- Map docling output to canonical `DocumentElement` records preserving page, bounding
  box, hierarchy, source offsets, structured payload, and extraction confidence.
- Make parsing deterministic and profile-versioned for retry and reindex safety.
- Provide regression fixtures and tests for supported formats.
- Record the decision in the architecture and ingestion foundation artifacts.

**Non-Goals:**

- Scanned-PDF OCR, DOCX, PPTX, XLSX, HTML, email, images, chart understanding, and
  code-AST parsing, even where docling supports them.
- Intake, source versioning, normalization, classification, chunking, embedding,
  indexing, and ingestion operations; those remain in `rag-ingestion-foundation`.
- A browser ingestion interface, parser profile management UI, or quota/billing.
- Migrating the Node BullMQ worker to Python or giving the worker direct catalog writes.

## Decisions

### The document parser is a provider port, not a domain dependency

A `DocumentParser` `Protocol` is added to `app/domain/rag/adapter_ports.py` alongside
`ObjectStoreAdapter`, `QueueAdapter`, and `VectorStoreAdapter`. Every method requires a
`TenantContext` and a source reference and returns ordered `DocumentElement` records.
Domain and application code never import docling; only the infrastructure adapter does.

The port returns the canonical value objects defined by the architecture
(`id`, `type`, `text`, `page`, `bounding_box`, `hierarchy_path`, `source_offsets`,
`structured_payload`, `extraction_confidence`), so the adapter owns the
`DoclingDocument` → `DocumentElement` translation and the domain stays parser-neutral.

Alternatives considered:

- Calling docling directly from the ingestion worker couples the pipeline to one
  parser and blocks future provider swaps.
- Returning a flattened string violates the canonical-element requirement and loses
  page, hierarchy, and source offsets needed for citation and chunking.

### Docling is the first supported parser adapter

A `DoclingParserAdapter` in `app/infrastructure/rag/parsers/` implements the port using
`docling.document_converter.DocumentConverter`. It is selected through parser-profile
configuration, not hard-coded. The mapping is:

| Canonical field | Docling source |
| --- | --- |
| `id` | item self reference |
| `type` | item label mapped to `title | narrative | list | table | image | code | formula` |
| `text` | item text |
| `page` | item provenance page number |
| `bounding_box` / `source_offsets` | item provenance bounding box |
| `hierarchy_path` | derived from the heading tree |
| `structured_payload` | table grid for `TableItem` |
| `extraction_confidence` | layout model confidence |

PDF elements retain page and reading order; Markdown preserves headings and code
blocks; TXT becomes ordered narrative elements.

Alternatives considered:

- Unstructured.io is referenced in the current architecture, but its open-source
  `hi_res` path requires heavy, install-fragile models and the project is pivoting
  toward a hosted API, which conflicts with the local-first goal.
- PyMuPDF and pdfplumber are lighter for digital-PDF text but do not provide layout
  elements, table grids, hierarchy, or extraction confidence, so the canonical-element
  contract would have to be hand-built and would not cover future formats.

### Parsing is deterministic and profile-versioned

The system persists an immutable, versioned parser profile identifying the docling
pipeline option, model identifier, OCR toggle, and format options. The same source bytes
plus the same parser profile produce identical canonical elements and element
identifiers on retry. A profile change creates a new generation and never mutates parsed
artifacts in place, matching the pipeline-fingerprint and reindex contract in the
ingestion foundation.

### Parsing runs in the worker, not the request path

The `DocumentParser` port is invoked only by the ingestion worker parse stage. FastAPI
may validate and select parser profiles but must not run docling conversion in an HTTP
request. The worker rejects any job whose tenant scope is missing or does not match the
deployment tenant. Parser artifacts are persisted under the tenant object namespace so
chunking and reindex can run without re-parsing, including OCR when a later change adds
it.

### Scope is limited to officially supported formats

The adapter officially supports digital PDF, Markdown, and plain text for v1 to match
the ingestion MVP. Scanned-PDF OCR, DOCX, PPTX, XLSX, HTML, email, images, charts, and
code-AST parsing are explicitly deferred to a later format-extension change, even where
docling supports them. Unsupported MIME types are rejected as unsupported for v1.

## Risks / Trade-offs

- [Docling layout models add worker weight and install complexity] → Pin docling and
  model versions, isolate the dependency to the worker runtime profile, and keep the
  FastAPI request path free of docling conversion.
- [Parser behavior varies by PDF quality] → Restrict v1 to digital PDF, Markdown, and
  TXT, persist parser artifacts, expose per-element confidence and a quality summary,
  and route low-quality extraction to `NEEDS_REVIEW` or a bounded fallback.
- [Future parser swaps are blocked by coupling] → Keep docling in infrastructure behind
  the domain port, map to canonical value objects, and select the adapter by profile.
- [Retries could create duplicate elements] → Use deterministic element identifiers
  derived from version, hierarchy path, offsets, content type, and parser-profile
  version, and persist artifacts idempotently.
- [Deferred formats may be requested early] → Explicitly reject unsupported MIME types
  for v1 and document the deferred formats and the later extension change.
- [Architecture references still point to Unstructured] → Update the architecture
  references and close the ingestion foundation open question as explicit tasks.

## Migration Plan

1. Confirm `rag-platform-foundation` provider ports and tenant context are available.
2. Add the `DocumentParser` port and `DocumentElement` / `ParserProfile` value objects
   with unit tests for tenant scope and canonical output.
3. Add the docling dependency and worker runtime profile; implement the
   `DoclingParserAdapter` and the `DoclingDocument` → `DocumentElement` mapping.
4. Add parser-profile configuration, deterministic identifiers, and reproducibility
   tests.
5. Add regression fixtures for digital PDF, Markdown, and TXT and run contract tests.
6. Update architecture references and the ingestion foundation open question; run the
   full repository quality gate and record the handoff to `rag-ingestion-foundation`
   task 3.1.

Rollback removes the docling dependency and adapter before any ingestion uses it.
Parser artifacts, once written by ingestion, are retained for recovery and are not
treated as a rollback authority.

## Open Questions

- Should the v1 docling pipeline use the default layout pipeline, a faster native path
  for digital PDFs, or a configurable choice between them?
- Should the adapter expose docling table structure as `structured_payload` now or defer
  table-structured extraction to the later format-extension change?
- Which docling model and version become the first pinned, officially supported profile
  for the local-first open-source deployment?
- Should a lightweight in-process fallback parser be provided for environments where
  docling models cannot be downloaded, or is docling a hard prerequisite?
