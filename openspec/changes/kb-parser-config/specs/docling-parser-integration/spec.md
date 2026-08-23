## MODIFIED Requirements

### Requirement: Parse stage selects adapter from IngestionConfig.parser
The parse stage SHALL read `cfg.parser` from the per-KB `IngestionConfig` (loaded
earlier in `parse_document()`) and select the adapter accordingly, replacing the
current logic that only checks `Settings.docling_serve_url`:

- `"docling_serve"` → instantiate `DoclingServeAdapter` using `cfg.docling_serve_url`
  if set, otherwise fall back to `Settings.docling_serve_url`. If neither is set,
  raise `DomainError("DOCLING_SERVE_URL_NOT_CONFIGURED", ..., 500)`.
- `"docling_inprocess"` → instantiate `DoclingParserAdapter` directly, no fallback.
  If docling is not installed, raise `DomainError("PARSER_NOT_INSTALLED", ..., 500)`
  without falling back to pdfminer.
- `"pdfminer"` → call `_extract_text()` directly, skip all docling adapters.
- `"auto"` → existing chain: serve (if `Settings.docling_serve_url` set) →
  in-process (if docling installed) → pdfminer.

#### Scenario: parser=docling_serve uses KB URL first
- **GIVEN** KB config has `parser="docling_serve"` and `docling_serve_url="http://kb-serve:5001"`
- **WHEN** `parse_document()` is called
- **THEN** `DoclingServeAdapter` is instantiated with `base_url="http://kb-serve:5001"`
- **AND** `Settings.docling_serve_url` is NOT used

#### Scenario: parser=docling_serve falls back to Settings URL
- **GIVEN** KB config has `parser="docling_serve"` and `docling_serve_url=None`
- **AND** `Settings.docling_serve_url="http://global-serve:5001"`
- **WHEN** `parse_document()` is called
- **THEN** `DoclingServeAdapter` is instantiated with `base_url="http://global-serve:5001"`

#### Scenario: parser=docling_serve with no URL raises
- **GIVEN** KB config has `parser="docling_serve"`, `docling_serve_url=None`
- **AND** `Settings.docling_serve_url` is also `None`
- **WHEN** `parse_document()` is called
- **THEN** `DomainError` with code `DOCLING_SERVE_URL_NOT_CONFIGURED` is raised

#### Scenario: parser=docling_inprocess uses in-process adapter only
- **GIVEN** KB config has `parser="docling_inprocess"`
- **WHEN** `parse_document()` is called
- **THEN** `DoclingParserAdapter` is used directly without checking `Settings.docling_serve_url`

#### Scenario: parser=pdfminer bypasses docling entirely
- **GIVEN** KB config has `parser="pdfminer"`
- **WHEN** `parse_document()` is called
- **THEN** `_extract_text()` is called directly without any docling adapter

#### Scenario: parser=auto preserves existing chain
- **GIVEN** KB config has `parser="auto"` (or no config exists)
- **WHEN** `parse_document()` is called
- **THEN** adapter selection follows the existing chain: serve → in-process → pdfminer
