## MODIFIED Requirements

### Requirement: IngestionConfig entity includes parser and docling_serve_url fields
The `IngestionConfig` domain entity SHALL include `parser: str` and
`docling_serve_url: str | None` fields. The `IngestionConfigRepository.upsert()`
protocol MUST accept these fields. `INGESTION_CONFIG_DEFAULTS` MUST set
`parser="auto"` and `docling_serve_url=None`.

#### Scenario: Upsert with parser fields persists correctly
- **WHEN** `upsert()` is called with `parser="docling_serve"` and a valid URL
- **THEN** `get_by_kb()` returns the same values

#### Scenario: Defaults include parser fields
- **WHEN** `INGESTION_CONFIG_DEFAULTS` is used
- **THEN** `parser` equals `"auto"` and `docling_serve_url` is `None`

### Requirement: Ingestion config API exposes parser fields
The ingestion config GET and upsert endpoints SHALL include `parser` and
`docling_serve_url` in both request and response Pydantic schemas. The API
response MUST always include both fields even when returning defaults.

#### Scenario: GET response includes parser fields
- **WHEN** client GETs ingestion config for a KB with no stored config
- **THEN** response body includes `"parser": "auto"` and `"docling_serve_url": null`

#### Scenario: Upsert request accepts parser fields
- **WHEN** client sends PATCH with `{"parser": "pdfminer"}`
- **THEN** the update is accepted and subsequent GET returns `"parser": "pdfminer"`
