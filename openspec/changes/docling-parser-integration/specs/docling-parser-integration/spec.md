## ADDED Requirements

### Requirement: DoclingParserAdapter is primary parser in parse stage
The parse stage SHALL use `DoclingParserAdapter` as the primary parser when docling is installed. The stage MUST instantiate a default `ParserProfile` and call `DoclingParserAdapter.parse()` with the document bytes, MIME type, and profile ID. The existing `_extract_text()` / `_extract_pdf()` dispatch MUST NOT be called when docling is available.

#### Scenario: PDF document parsed with docling installed
- **GIVEN** docling is installed (`uv sync --extra parsing`)
- **WHEN** `parse_document()` is called with a document version whose MIME type is `application/pdf`
- **THEN** `DoclingParserAdapter.parse()` MUST be called with the raw bytes and MIME type
- **AND** the returned `ParsedDocument` elements MUST be serialized to text and stored in `_parsed_cache`

#### Scenario: Markdown document parsed with docling installed
- **GIVEN** docling is installed
- **WHEN** `parse_document()` is called with a document version whose MIME type is `text/markdown`
- **THEN** `DoclingParserAdapter.parse()` MUST be called with the raw bytes and MIME type
- **AND** the returned `ParsedDocument` elements MUST be serialized to text

#### Scenario: Plain text document parsed with docling installed
- **GIVEN** docling is installed
- **WHEN** `parse_document()` is called with a document version whose MIME type is `text/plain`
- **THEN** `DoclingParserAdapter.parse()` MUST be called with the raw bytes and MIME type

---

### Requirement: Graceful fallback to pdfminer when docling is not installed
When docling is not installed, the parse stage SHALL fall back to the existing `pdfminer`-based extraction without raising an unhandled exception. The fallback MUST log a warning indicating that docling is unavailable and pdfminer is being used. The pipeline MUST continue normally using the fallback output.

#### Scenario: Docling not installed — PDF fallback
- **GIVEN** docling is NOT installed (no `uv sync --extra parsing`)
- **WHEN** `parse_document()` is called with `application/pdf`
- **THEN** the stage MUST catch `ImportError` or `DomainError("PARSER_NOT_INSTALLED")`
- **AND** MUST log a warning that docling is unavailable
- **AND** MUST fall back to `_extract_pdf()` using pdfminer
- **AND** MUST return extracted text normally without raising

#### Scenario: Docling not installed — non-PDF fallback
- **GIVEN** docling is NOT installed
- **WHEN** `parse_document()` is called with `text/plain` or `text/markdown`
- **THEN** the stage MUST fall back to `_extract_text()` UTF-8 decode path
- **AND** MUST log a warning that docling is unavailable

#### Scenario: Docling raises unexpected error — no silent swallow
- **GIVEN** docling is installed but raises a non-import, non-profile error during conversion
- **WHEN** `parse_document()` is called
- **THEN** the stage MUST NOT silently swallow the error
- **AND** MUST allow the exception to propagate so the worker can mark the job as failed

---

### Requirement: Default ParserProfile is instantiated in parse stage
The parse stage SHALL construct a single hardcoded default `ParserProfile` instance to pass to `DoclingParserAdapter`. The profile MUST have a stable `id`, `pipeline`, `model`, and `ocr_enabled` value. No database lookup or dynamic profile resolution is required in this change.

#### Scenario: Default profile fields are correct
- **WHEN** the default `ParserProfile` is constructed in `parse_document()`
- **THEN** it MUST have `id="default-v1"`, `pipeline="standard"`, `model="layout"`, `ocr_enabled=False`, and `version="1"`

#### Scenario: Profile ID passed to adapter matches default
- **WHEN** `DoclingParserAdapter.parse()` is called
- **THEN** the `parser_profile_id` argument MUST equal the `id` field of the default `ParserProfile`

---

### Requirement: ParsedDocument is serialized to plain text for downstream compatibility
The `ParsedDocument` returned by `DoclingParserAdapter.parse()` SHALL be serialized to a single plain-text string before being stored in `_parsed_cache`. Serialization MUST join the `text` field of each `DocumentElement` in order, separated by newline characters. Empty element texts MUST be excluded from the join.

#### Scenario: Elements serialized in order
- **WHEN** `ParsedDocument.elements` contains N elements with non-empty `text`
- **THEN** the serialized string MUST be `"\n".join(e.text for e in elements if e.text.strip())`
- **AND** the result MUST preserve document reading order

#### Scenario: All elements have empty text
- **WHEN** all `DocumentElement` records have empty or whitespace-only `text`
- **THEN** the serialized string MUST be an empty string `""`
- **AND** the stage MUST NOT raise

#### Scenario: Serialized text stored in cache
- **WHEN** serialization completes
- **THEN** `_parsed_cache[document_version_id]` MUST contain the serialized text string
- **AND** `parse_document()` MUST return that string

---

### Requirement: Tenant context is constructed for adapter call
`DoclingParserAdapter.parse()` requires a `TenantContext`. The parse stage SHALL construct a `TenantContext` from the `tenant_id` parameter and pass it to the adapter. The adapter's `expected_tenant_id` constructor argument MUST match `tenant_id`.

#### Scenario: Tenant context matches adapter expectation
- **WHEN** `parse_document()` is called with `tenant_id="t1"`
- **THEN** `DoclingParserAdapter` MUST be constructed with `expected_tenant_id="t1"`
- **AND** `TenantContext(tenant_id="t1")` MUST be passed as the `tenant` argument to `parse()`

#### Scenario: Tenant mismatch raises DomainError
- **WHEN** the adapter is constructed with one `expected_tenant_id` but `parse()` receives a different `TenantContext`
- **THEN** a `DomainError` with code `TENANT_SCOPE_MISMATCH` MUST be raised
- **AND** the error MUST propagate out of `parse_document()`

---

### Requirement: pyproject.toml declares docling as optional parsing dependency
The `apps/api/pyproject.toml` MUST declare `docling>=2.118.0` under `[project.optional-dependencies] parsing`. The core dependency list MUST NOT include docling so the API runs without the heavy ML dependency.

#### Scenario: Docling in optional extras only
- **WHEN** `pyproject.toml` is inspected
- **THEN** `docling` MUST appear under `[project.optional-dependencies] parsing`
- **AND** `docling` MUST NOT appear in the top-level `[project] dependencies` list
