## Context

The parse stage (`workers/stages/parse.py`) currently calls `_extract_text()` which dispatches to `_extract_pdf()` (pdfminer) for PDFs and UTF-8 decode for text/markdown. It produces a flat string with no structure. `DoclingParserAdapter` in `infrastructure/rag/parsers/docling_adapter.py` already implements the `DocumentParser` protocol and produces rich `ParsedDocument` with typed `DocumentElement` records — but it has never been connected to the worker.

**Current state:**
- `parse_document()` calls `_extract_text()` → `_extract_pdf()` for PDFs, plain decode for others
- `DoclingParserAdapter` exists, is fully implemented, uses lazy docling import
- `mapping.py` maps docling output to canonical `DocumentElement` records
- `ParserProfile` domain value object exists but is never instantiated in the worker
- `TenantContext` exists but is not constructed in the parse stage
- `docling>=2.118.0` is already declared under `[project.optional-dependencies] parsing`

**Constraints:**
- Chunking stage receives a `str` from `_parsed_cache` — this interface must not change
- Fallback to pdfminer must work when docling is not installed
- No new DB tables, migrations, or profile resolution logic in this change
- `DoclingParserAdapter.parse()` is `async` — the stage already runs in an async context

## Goals / Non-Goals

**Goals:**
- Wire `DoclingParserAdapter` as primary parser in `parse_document()`
- Construct a hardcoded default `ParserProfile` (no DB lookup)
- Construct `TenantContext` from existing `tenant_id` parameter
- Serialize `ParsedDocument` to plain text for downstream compatibility
- Graceful fallback to pdfminer with logged warning when docling is absent

**Non-Goals:**
- Persisting `DocumentElement` records to DB (that is `parsed-text-persistence`)
- Dynamic profile resolution or DB-backed `ParserProfile` lookup
- Changing the chunking or embedding stages
- Modifying `DoclingParserAdapter`, `mapping.py`, or domain entities
- Adding new MIME type support beyond what `SUPPORTED_MIME_TYPES` already covers

## Decisions

### Decision 1: Wrap adapter call in try/except for graceful fallback

**Choice:** Catch `ImportError` and `DomainError` with code `PARSER_NOT_INSTALLED` around the adapter call. On either exception, log a warning and fall through to the existing `_extract_text()` path.

**Rationale:**
- `DoclingParserAdapter._convert()` raises `DomainError("PARSER_NOT_INSTALLED")` on `ImportError` — we must catch `DomainError` not just `ImportError` since the lazy import is inside the adapter
- Fallback keeps the pipeline working in dev/CI environments where docling is not installed
- A logged warning makes the degraded state observable without crashing the worker

**Alternatives considered:**
- **Check `importlib.util.find_spec("docling")` before instantiating**: Rejected — the adapter already handles the lazy import check internally; duplicating it couples the stage to adapter internals
- **Raise and fail the job when docling is missing**: Rejected — too strict for environments that don't need rich parsing; fallback is the specified behavior

### Decision 2: Hardcode default ParserProfile in parse stage

**Choice:** Construct `ParserProfile(id="default-v1", pipeline="standard", model="layout", ocr_enabled=False, version="1")` inline in `parse_document()`.

**Rationale:**
- No DB-backed profile resolution is in scope for this change
- The profile ID only needs to be stable and match the adapter's check — a module-level constant achieves this with zero complexity
- A future change can replace this with a DB lookup without touching the adapter contract

**Alternatives considered:**
- **Load profile from settings**: Rejected — adds config surface area without real benefit at this stage; hardcoded default is explicitly specified
- **Pass profile as a parameter to `parse_document()`**: Rejected — would change the function signature and all callers; out of scope

### Decision 3: Serialize ParsedDocument as newline-joined element texts

**Choice:** `"\n".join(e.text for e in parsed_doc.elements if e.text.strip())`

**Rationale:**
- Preserves document reading order (elements are already sorted by page + prov_index in `mapping.py`)
- Newline separation maintains paragraph boundaries that chunking can use
- Empty elements (figures without captions, empty headers) are excluded to avoid blank chunks
- The chunking stage receives identical `str` type — zero interface change

**Alternatives considered:**
- **Include element type markers** (`"[TABLE]\n...\n[/TABLE]"`): Rejected — out of scope for this change; would affect chunking stage behavior
- **Join with double newline**: Considered — single newline is sufficient and matches pdfminer's typical output density

### Decision 4: Construct TenantContext inline from tenant_id

**Choice:** `TenantContext(tenant_id=tenant_id)` constructed inside `parse_document()` and passed to the adapter along with `expected_tenant_id=tenant_id`.

**Rationale:**
- `parse_document()` already receives `tenant_id` as a parameter
- `TenantContext` is a simple value object — no injection needed
- Adapter's `assert_tenant_scope` will always pass since both sides use the same `tenant_id`

**Alternatives considered:**
- **Add TenantContext as a parameter to `parse_document()`**: Rejected — changes the call signature; the existing parameter is sufficient

### Decision 5: Module-level DEFAULT_PARSER_PROFILE constant

**Choice:** Define `_DEFAULT_PARSER_PROFILE` as a module-level constant in `parse.py` so it is constructed once, not on every invocation.

**Rationale:**
- `ParserProfile` is frozen (`frozen=True` dataclass) — safe as a constant
- Avoids re-constructing the object on every job execution
- Keeps `parse_document()` body clean

## Risks / Trade-offs

**[Risk]** DomainError codes other than `PARSER_NOT_INSTALLED` might be swallowed by a broad catch  
→ **Mitigation:** Only catch `DomainError` when `error.code == "PARSER_NOT_INSTALLED"` (or catch `ImportError` separately); let other `DomainError` codes propagate

**[Risk]** Docling conversion is CPU/memory-heavy and may time out in constrained worker environments  
→ **Mitigation:** Out of scope for this change; worker timeout configuration is a separate ops concern; fallback ensures the job doesn't fail silently

**[Risk]** Serialized text from docling may differ from pdfminer output, affecting existing chunk quality  
→ **Mitigation:** Expected and intentional — docling output is structurally richer; chunking stage is unaffected by content differences

**[Trade-off]** Rich `DocumentElement` data (bounding boxes, tables, hierarchy) is serialized away in this change  
→ **Benefit:** Keeps the blast radius of this change small; element persistence is deferred to `parsed-text-persistence` which is the correct place for it

## Migration Plan

**Deployment steps:**
1. Verify `docling>=2.118.0` present in `pyproject.toml` under `parsing` extra (already done)
2. Add `_DEFAULT_PARSER_PROFILE` constant and `TenantContext` import to `parse.py`
3. Replace `_extract_text()` call with `DoclingParserAdapter.parse()` wrapped in fallback logic
4. Add serialization helper `_serialize_parsed_document()`
5. Run unit tests: docling path, fallback path, serialization, profile fields
6. Deploy — environments without docling continue using pdfminer automatically

**Rollback strategy:**
- Revert `parse.py` to the previous `_extract_text()` call — single-file change, no migrations
- `DoclingParserAdapter` is untouched — no infrastructure rollback needed

**Validation:**
- Unit tests cover both code paths (docling installed / not installed)
- Manual test: ingest a PDF and verify `_parsed_cache` contains non-empty text
- Confirm chunking stage receives the same `str` type as before

## Open Questions

None — design is ready for implementation. Profile persistence and `DocumentElement` DB storage are deferred to `parsed-text-persistence`.
