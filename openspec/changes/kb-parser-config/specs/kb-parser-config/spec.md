## Purpose

Per-KB parser selection and optional docling-serve URL stored in the database,
editable by admin via API, consumed by the ingestion parse stage to select the
correct document parser adapter for each knowledge base.

## ADDED Requirements

### Requirement: IngestionConfig carries parser selection and optional serve URL
The `IngestionConfig` domain entity SHALL include a `parser` field with values
`"auto" | "docling_serve" | "docling_inprocess" | "pdfminer"` and a
`docling_serve_url: str | None` field. The default value for `parser` MUST be
`"auto"` and for `docling_serve_url` MUST be `None` in `INGESTION_CONFIG_DEFAULTS`.

#### Scenario: Default config uses auto parser
- **WHEN** no ingestion config exists for a KB
- **THEN** `INGESTION_CONFIG_DEFAULTS.parser` equals `"auto"`
- **AND** `INGESTION_CONFIG_DEFAULTS.docling_serve_url` is `None`

#### Scenario: Config with explicit parser is persisted and returned
- **WHEN** admin upserts config with `parser="docling_serve"` and `docling_serve_url="http://serve:5001"`
- **THEN** subsequent `get_by_kb` returns the same `parser` and `docling_serve_url` values

### Requirement: Parser field is validated on upsert
The ingestion config service SHALL reject `parser` values outside the allowed set
with `DomainError("VALIDATION_ERROR", ..., 422)`. When `parser="docling_serve"`,
the service MUST validate that `docling_serve_url` is a non-empty HTTP/HTTPS URL.
When `parser` is any other value, `docling_serve_url` MAY be `None`.

#### Scenario: Invalid parser value is rejected
- **WHEN** admin upserts config with `parser="unknown_parser"`
- **THEN** `DomainError` with code `VALIDATION_ERROR` is raised before any DB write

#### Scenario: docling_serve parser without URL is rejected
- **WHEN** admin upserts config with `parser="docling_serve"` and `docling_serve_url=None`
- **THEN** `DomainError` with code `VALIDATION_ERROR` is raised

#### Scenario: docling_serve parser with invalid URL is rejected
- **WHEN** admin upserts config with `parser="docling_serve"` and `docling_serve_url="not-a-url"`
- **THEN** `DomainError` with code `VALIDATION_ERROR` is raised

### Requirement: Parser config is exposed via ingestion config API
The ingestion config GET and PATCH/PUT endpoints SHALL include `parser` and
`docling_serve_url` in request and response bodies. The API MUST accept all
four `parser` values. `docling_serve_url` MUST be `null` in responses when not set.

#### Scenario: GET returns parser config
- **WHEN** admin GETs ingestion config for a KB
- **THEN** response includes `parser` and `docling_serve_url` fields

#### Scenario: PATCH updates parser config
- **WHEN** admin PATCHes ingestion config with `parser="docling_inprocess"`
- **THEN** subsequent GET returns `parser="docling_inprocess"`

### Requirement: DB columns are added via Alembic migration
The `rag_kb_ingestion_configs` table SHALL gain two new nullable columns:
`parser VARCHAR(32) NOT NULL DEFAULT 'auto'` and
`docling_serve_url VARCHAR(2048) NULL`. The migration MUST be reversible (downgrade
removes the columns). Existing rows MUST get `parser='auto'` and
`docling_serve_url=NULL` after upgrade without manual intervention.

#### Scenario: Migration upgrades existing rows
- **WHEN** Alembic upgrade runs on a DB with existing ingestion config rows
- **THEN** all existing rows have `parser='auto'` and `docling_serve_url=NULL`

#### Scenario: Migration is reversible
- **WHEN** Alembic downgrade runs
- **THEN** both columns are removed without data loss in other columns
