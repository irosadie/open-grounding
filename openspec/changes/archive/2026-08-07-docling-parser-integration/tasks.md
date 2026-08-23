## 1. Verify Dependencies

- [x] 1.1 Confirm `docling>=2.118.0` is present under `[project.optional-dependencies] parsing` in `apps/api/pyproject.toml` and is absent from core dependencies

## 2. Wire Adapter into Parse Stage

- [x] 2.1 Add `_DEFAULT_PARSER_PROFILE` module-level constant to `apps/api/app/workers/stages/parse.py` with `id="default-v1"`, `pipeline="standard"`, `model="layout"`, `ocr_enabled=False`, `version="1"`
- [x] 2.2 Add `_serialize_parsed_document()` helper in `parse.py` that joins non-empty `element.text` values with `"\n"`
- [x] 2.3 Add `TenantContext` import and `DoclingParserAdapter` import to `parse.py`
- [x] 2.4 Replace the `_extract_text()` call in `parse_document()` with an `async` call to `DoclingParserAdapter.parse()` using `_DEFAULT_PARSER_PROFILE` and `TenantContext(tenant_id=tenant_id)`
- [x] 2.5 Wrap the adapter call in try/except: catch `ImportError` and `DomainError` with code `PARSER_NOT_INSTALLED`, log a warning, and fall back to `_extract_text()`

## 3. Tests

- [x] 3.1 Unit test: docling installed path — `DoclingParserAdapter.parse()` is called and serialized text is returned and stored in `_parsed_cache`
- [x] 3.2 Unit test: docling not installed path — `DomainError("PARSER_NOT_INSTALLED")` triggers fallback to `_extract_text()`, warning is logged, text returned normally
- [x] 3.3 Unit test: `_serialize_parsed_document()` — joins non-empty element texts in order, skips whitespace-only elements, returns `""` when all elements are empty
- [x] 3.4 Unit test: `_DEFAULT_PARSER_PROFILE` fields match spec (`id`, `pipeline`, `model`, `ocr_enabled`, `version`)
- [x] 3.5 Unit test: non-`PARSER_NOT_INSTALLED` `DomainError` from adapter propagates and is not swallowed
