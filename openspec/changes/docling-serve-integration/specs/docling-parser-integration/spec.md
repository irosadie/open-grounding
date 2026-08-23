## MODIFIED Requirements

### Requirement: DoclingServeAdapter is preferred when DOCLING_SERVE_URL is set
The parse stage SHALL try `DoclingServeAdapter` first when `Settings.docling_serve_url`
is not `None`. Only when `DOCLING_SERVE_URL` is absent SHALL the stage fall back to the
in-process `DoclingParserAdapter` (when docling is installed) and then to `pdfminer`.
The fallback chain MUST be: `DoclingServeAdapter` → `DoclingParserAdapter` →
`pdfminer`. No silent fallback from `DoclingServeAdapter` to `DoclingParserAdapter`
occurs at runtime — if the serve adapter raises, the error propagates to the worker.
`_parse_with_docling_or_fallback()` MUST accept `settings: Settings` as a parameter
and use it to determine which adapter to instantiate.

#### Scenario: DOCLING_SERVE_URL is set — serve adapter is used
- **GIVEN** `DOCLING_SERVE_URL` is configured in settings
- **WHEN** `parse_document()` is called for any supported MIME type
- **THEN** `DoclingServeAdapter.parse()` is called
- **AND** the in-process `DoclingParserAdapter` is NOT instantiated

#### Scenario: DOCLING_SERVE_URL is absent — in-process adapter is used
- **GIVEN** `DOCLING_SERVE_URL` is not set and docling is installed
- **WHEN** `parse_document()` is called
- **THEN** `DoclingParserAdapter.parse()` is called as before
- **AND** `DoclingServeAdapter` is NOT instantiated

#### Scenario: DOCLING_SERVE_URL is absent and docling not installed — pdfminer fallback
- **GIVEN** `DOCLING_SERVE_URL` is not set and docling is NOT installed
- **WHEN** `parse_document()` is called with `application/pdf`
- **THEN** the stage falls back to `pdfminer` as before

#### Scenario: DoclingServeAdapter raises — error propagates
- **GIVEN** `DOCLING_SERVE_URL` is set
- **WHEN** `DoclingServeAdapter.parse()` raises a `DomainError`
- **THEN** the error propagates to the worker without silent swallowing
- **AND** the worker marks the job as failed

### Requirement: Parse stage passes shared httpx.AsyncClient to DoclingServeAdapter
The parse stage SHALL maintain a module-level shared `httpx.AsyncClient` instance
configured with appropriate timeouts. This client MUST be passed to
`DoclingServeAdapter` at instantiation time and reused across all jobs in the same
worker process. The client MUST be initialised lazily on first use and MUST NOT be
re-created per job.

#### Scenario: Client is initialised once and reused
- **WHEN** `parse_document()` is called multiple times in the same worker process
  with `DOCLING_SERVE_URL` set
- **THEN** the same `httpx.AsyncClient` instance is passed to each `DoclingServeAdapter`

### Requirement: Parse stage emits dev_trace span covering docling-serve conversion
The parse stage SHALL emit a `tracer.op("ingestion.parse.docling_serve", ...)` span
that wraps the full `DoclingServeAdapter.parse()` call, recording `version_id`,
`chars`, `task_id`, and `elapsed_seconds` in the span metadata. This follows the
existing `tracer.op("ingestion.parse", ...)` pattern already used in the stage.

#### Scenario: Span is emitted with correct metadata
- **WHEN** `DoclingServeAdapter.parse()` completes
- **THEN** a dev_trace span `ingestion.parse.docling_serve` is recorded with
  `version_id`, `chars`, and `task_id` in its metadata
