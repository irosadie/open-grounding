## Purpose

HTTP-based document parser adapter that delegates PDF and document conversion to a
remote `docling-serve` instance via its async REST API, implements the `DocumentParser`
port, and is selected by the parse stage when `DOCLING_SERVE_URL` is configured.

## ADDED Requirements

### Requirement: DoclingServeAdapter implements the DocumentParser port
The system SHALL provide a `DoclingServeAdapter` class that implements the
`DocumentParser` port. It MUST accept the same `parse()` signature as
`DoclingParserAdapter` and return a `ParsedDocument`. Domain and application code MUST
NOT import docling SDK types through this adapter.

#### Scenario: Adapter is used as a DocumentParser
- **WHEN** `DoclingServeAdapter` is instantiated and `parse()` is called with tenant
  context, source bytes, MIME type, and parser profile ID
- **THEN** it returns a `ParsedDocument` with ordered canonical elements without
  importing any local docling SDK

### Requirement: Adapter submits file to docling-serve async endpoint
The adapter SHALL submit the source bytes to `POST /v1/convert/file/async` on the
configured `DOCLING_SERVE_URL`. The request MUST be a multipart form upload with the
file bytes. The adapter MUST capture the returned `task_id`.

#### Scenario: File is submitted successfully
- **WHEN** `parse()` is called with valid PDF bytes
- **THEN** the adapter POSTs the bytes to `/v1/convert/file/async` and receives a
  `task_id` in the response

#### Scenario: Submit fails with HTTP error
- **WHEN** the docling-serve endpoint returns a non-2xx status
- **THEN** the adapter raises a `DomainError` with code `DOCLING_SERVE_SUBMIT_ERROR`
  and includes the HTTP status and response body in `details`

### Requirement: Adapter polls until task completes or times out
After submitting, the adapter SHALL poll `GET /v1/status/poll/{task_id}` at a
configurable interval until `task_status` is `success` or `failed`, or until a
configurable timeout is exceeded. Poll interval and timeout MUST be read from
`Settings` (`docling_serve_poll_interval_seconds`, `docling_serve_timeout_seconds`).
The adapter MUST raise `DomainError(DOCLING_SERVE_TIMEOUT)` on timeout and
`DomainError(DOCLING_SERVE_TASK_FAILED)` when status is `failed`. The first poll
MUST happen immediately after submit without waiting one full interval.

#### Scenario: Task completes successfully
- **WHEN** polling returns `task_status: success`
- **THEN** the adapter proceeds to fetch the result without raising

#### Scenario: Task fails on docling-serve side
- **WHEN** polling returns `task_status: failed`
- **THEN** the adapter raises `DomainError` with code `DOCLING_SERVE_TASK_FAILED`
  and includes `task_id` and `error_message` from the response in `details`

#### Scenario: Polling exceeds timeout
- **WHEN** the task has not reached a terminal status within `docling_serve_timeout_seconds`
- **THEN** the adapter raises `DomainError` with code `DOCLING_SERVE_TIMEOUT`
  and includes `task_id` and elapsed seconds in `details`

#### Scenario: Poll request itself fails with HTTP error
- **WHEN** a poll request returns a non-2xx status
- **THEN** the adapter raises `DomainError` with code `DOCLING_SERVE_POLL_ERROR`

### Requirement: Adapter fetches and maps result to ParsedDocument
After a successful poll, the adapter SHALL fetch `GET /v1/result/{task_id}` and map
the `md_content` field from the response into a `ParsedDocument`. Each non-empty line
of the markdown content MUST become a `DocumentElement` with type `paragraph`.
The `ParserQualitySummary` MUST be populated from the response `confidence` object:
`mean_score` → `aggregate_confidence`, `parse_score` → `text_coverage`,
`layout_score` → `page_coverage`. `element_count` MUST equal the number of elements
produced. `empty_element_ratio` MUST be computed from the mapped elements.

#### Scenario: Result is mapped to ParsedDocument elements
- **WHEN** the result endpoint returns `md_content` with N non-empty lines
- **THEN** the adapter returns a `ParsedDocument` with N `DocumentElement` records in
  order, each carrying the line text
- **AND** `quality.aggregate_confidence` equals `confidence.mean_score` from the response

#### Scenario: Result has empty md_content
- **WHEN** `md_content` is empty or null
- **THEN** the adapter returns a `ParsedDocument` with zero elements without raising
- **AND** `quality.text_coverage` is `0.0`

#### Scenario: Confidence object is absent from result
- **WHEN** the result response has no `confidence` field
- **THEN** `ParserQualitySummary` fields default to `None` / `0.0` without raising

#### Scenario: Fetch result fails with HTTP error
- **WHEN** the result endpoint returns a non-2xx status
- **THEN** the adapter raises `DomainError` with code `DOCLING_SERVE_RESULT_ERROR`

### Requirement: Adapter uses a shared httpx.AsyncClient with configured timeouts
The adapter SHALL accept an `httpx.AsyncClient` instance via constructor injection.
The client MUST be configured with `connect`, `read`, and `write` timeouts appropriate
for large file uploads and long-running conversions. The parse stage MUST NOT create a
new client per job — the client MUST be shared and reused across calls (connection
pooling). The adapter MUST NOT own the client lifecycle (no `async with` inside
`parse()`).

#### Scenario: Client is reused across multiple parse calls
- **WHEN** `parse()` is called multiple times with the same adapter instance
- **THEN** the same `httpx.AsyncClient` instance is used for all HTTP calls

#### Scenario: Client timeout is enforced
- **WHEN** the docling-serve endpoint does not respond within the configured read timeout
- **THEN** `httpx.ReadTimeout` propagates and the worker marks the job as failed

### Requirement: Adapter enforces tenant scope before any HTTP call
The adapter MUST call `assert_tenant_scope` before submitting any request to
docling-serve. A mismatched or missing tenant context MUST raise
`DomainError.tenant_scope_mismatch` before any network I/O occurs.

#### Scenario: Tenant mismatch is caught before HTTP call
- **WHEN** `parse()` is called with a `TenantContext` that does not match
  `expected_tenant_id`
- **THEN** `DomainError` with code `TENANT_SCOPE_MISMATCH` is raised before any
  HTTP request is made

### Requirement: Adapter rejects unsupported MIME types
The adapter SHALL reject MIME types not in `SUPPORTED_MIME_TYPES` before submitting to
docling-serve. It MUST raise `DomainError` with code `UNSUPPORTED_MIME_TYPE`.

#### Scenario: Unsupported MIME type is rejected
- **WHEN** `parse()` is called with a MIME type outside the supported set
- **THEN** `DomainError` with code `UNSUPPORTED_MIME_TYPE` is raised before any HTTP
  call is made

### Requirement: Parse stage emits dev_trace span for docling-serve conversion
The parse stage SHALL wrap the `DoclingServeAdapter.parse()` call in a
`tracer.op("ingestion.parse.docling_serve", ...)` span. The span MUST record
`version_id`, `chars` (length of serialized text), `task_id`, and `elapsed_seconds`.

#### Scenario: Dev trace span is emitted on success
- **WHEN** `DoclingServeAdapter.parse()` completes successfully
- **THEN** a `ingestion.parse.docling_serve` span is emitted with `task_id` and `chars`

### Requirement: DOCLING_SERVE_URL, timeout, and poll interval are configurable settings
The system SHALL read `docling_serve_url`, `docling_serve_timeout_seconds` (default
`120.0`), and `docling_serve_poll_interval_seconds` (default `3.0`) from the
environment via `Settings`. `docling_serve_url` MUST default to `None`. When
`DOCLING_SERVE_URL` is set, `Settings` MUST validate it is a non-empty HTTP/HTTPS URL.
`docling_serve_timeout_seconds` and `docling_serve_poll_interval_seconds` MUST be
validated as positive floats.

#### Scenario: URL setting is absent
- **WHEN** `DOCLING_SERVE_URL` is not set
- **THEN** `Settings.docling_serve_url` is `None` and the parse stage does not
  instantiate `DoclingServeAdapter`

#### Scenario: URL setting is present and valid
- **WHEN** `DOCLING_SERVE_URL=http://localhost:5001` is set
- **THEN** `Settings.docling_serve_url` equals `"http://localhost:5001"`

#### Scenario: URL setting is invalid
- **WHEN** `DOCLING_SERVE_URL=not-a-url` is set
- **THEN** `Settings` raises a `ValueError` at startup with a clear message

#### Scenario: Timeout setting is invalid
- **WHEN** `DOCLING_SERVE_TIMEOUT_SECONDS=0` or a negative value is set
- **THEN** `Settings` raises a `ValueError` at startup
