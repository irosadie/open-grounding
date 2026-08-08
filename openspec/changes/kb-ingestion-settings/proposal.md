## Why

Quality gate parameters are currently hardcoded in the backend constructor, the `max_invalid_char_ratio` threshold is declared but never evaluated, and there is no way for operators to force human review on every document regardless of quality scores. For production-grade deployments handling sensitive or regulated content, operators need per-KB control over ingestion quality behavior — without touching source code.

## What Changes

- Fix bug: `max_invalid_char_ratio` is declared in `QualityGate.__init__` but never checked in `evaluate()` — wire it in
- Add `IngestionConfig` entity per Knowledge Base storing quality gate thresholds + auto-review toggle
- New backend: `IngestionConfig` domain entity, repository protocol, ORM model, Alembic migration, CRUD endpoints
- New frontend: KB detail layout with tab shell (`[id]/layout.tsx`) wrapping existing sub-routes (Planner, Memory, Decomposition) + new Ingestion Settings tab
- KB list page: replace per-KB action buttons with a single "Open" link into the new detail layout
- Auto-review OFF: after parse + normalize, route ALL documents to `NEEDS_REVIEW` regardless of quality gate outcome

## Capabilities

### New Capabilities
- `kb-ingestion-config`: Per-KB ingestion configuration — quality gate thresholds (text coverage, invalid char ratio, aggregate confidence, page coverage) and auto-review toggle stored in PostgreSQL, editable via API and console UI
- `kb-detail-shell`: Knowledge Base detail page with tab navigation shell wrapping Planner, Memory, Decomposition, and Ingestion Settings sub-routes

### Modified Capabilities
- `rag-content-extraction-and-quality`: Quality gate now evaluates `max_invalid_char_ratio` (bug fix) and respects per-KB `auto_review` flag — when enabled, all documents are routed to `NEEDS_REVIEW` after parsing regardless of quality scores
- `rag-knowledge-catalog`: KB catalog now includes `IngestionConfig` as a child entity with its own lifecycle
- `rag-settings-console-ui`: KB list page navigation changes — action buttons replaced with single "Open" entry point into KB detail layout

## Impact

- **Backend**: new `IngestionConfig` ORM model + migration, new CRUD endpoints under `/rag/knowledge-bases/{kb_id}/ingestion-config`, `QualityGate.evaluate()` bug fix, parse stage reads per-KB config
- **Frontend**: new `[id]/layout.tsx` tab shell, new `ingestion/page.tsx` + `ingestion-content.tsx`, KB list refactor, new hook + schema + types for ingestion config
- **Database**: one new table `rag_kb_ingestion_configs` with FK to `rag_knowledge_bases`
- **No breaking changes** to existing ingestion API or document lifecycle states
