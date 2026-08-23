## Why

The current parse stage uses `pdfminer.six` which only extracts unstructured plain text. It produces no layout information, table data, image references, or element hierarchy. This severely limits downstream chunking quality: chunks can split mid-table, lose heading context, and discard structured data entirely. `DoclingParserAdapter` already exists in infrastructure and implements the `DocumentParser` protocol, but it has never been wired into the worker pipeline. This change connects the existing adapter as the primary parser so the ingestion pipeline produces rich, typed `DocumentElement` records instead of raw strings.

## What Changes

- Wire `DoclingParserAdapter` into `workers/stages/parse.py` as the primary parser, replacing the direct `_extract_text()` / `_extract_pdf()` calls
- Instantiate a default `ParserProfile` in the parse stage (hardcoded, no DB lookup required)
- Serialize `ParsedDocument` elements back to plain text (join `element.text` values) for compatibility with the existing chunking stage — no changes to downstream stages in this change
- Implement graceful fallback to `pdfminer.six` when docling is not installed (`ImportError` / `DomainError("PARSER_NOT_INSTALLED")`)
- Verify `docling>=2.118.0` is declared under `[project.optional-dependencies] parsing` in `pyproject.toml` (already present — no change required)

## Capabilities

### New Capabilities
- `docling-parser-integration`: Wire the existing `DoclingParserAdapter` into the parse worker stage so ingestion produces rich `DocumentElement` records with layout, table, and hierarchy data when docling is installed

### Modified Capabilities
- `parse-stage-text-extraction`: The parse stage now delegates to `DoclingParserAdapter` as primary parser with `pdfminer` as fallback, replacing the direct `_extract_text()` implementation

## Impact

**Affected code:**
- `apps/api/app/workers/stages/parse.py` — replace `_extract_text()` dispatch with `DoclingParserAdapter.parse()` call; add fallback; add `ParserProfile` instantiation
- `apps/api/pyproject.toml` — read-only verification; `docling>=2.118.0` already present under `parsing` extra

**Affected systems:**
- Ingestion worker pipeline — parse stage output changes from raw string to docling-derived text (semantically equivalent for existing chunking stage)
- Environments without `uv sync --extra parsing` — continue to work via pdfminer fallback

**Backward compatibility:**
- Chunking stage receives the same `str` type from `parse_document()` — no interface changes
- `_parsed_cache` stores text as before — no changes to cache contract
- Fallback ensures zero regression when docling is not installed

**Testing surface:**
- Unit test: docling installed path calls adapter and returns joined element text
- Unit test: docling not installed path falls back to pdfminer and logs warning
- Unit test: default `ParserProfile` is constructed with expected field values
- Unit test: `ParsedDocument` serialization joins all element texts with newline separator

**Dependency:**
- Depends on `parsed-text-persistence` being merged first so parsed text is persisted to DB before review workflows are unblocked
