## 1. Backend — Domain & Quality Gate Fix

- [x] 1.1 Fix `QualityGate.evaluate()` in `apps/api/app/domain/rag/normalizer.py` — wire `max_invalid_char_ratio` check using invalid char count computed from all elements text
- [x] 1.2 Add `compute_invalid_char_ratio()` helper in `normalizer.py` that scans element texts using `_INVALID_CHAR_RE` and returns ratio
- [x] 1.3 Add `IngestionConfig` domain entity in `apps/api/app/domain/rag/catalog.py` with fields: `id`, `knowledge_base_id`, `min_text_coverage`, `max_invalid_char_ratio`, `min_aggregate_confidence`, `min_page_coverage`, `auto_review`
- [x] 1.4 Add `IngestionConfigRepository` protocol in `apps/api/app/domain/rag/catalog.py` with `get_by_kb` (returns config or None) and `upsert` methods

## 2. Backend — Database & Migration

- [x] 2.1 Add `IngestionConfigRecord` ORM model in `apps/api/app/infrastructure/rag_catalog.py` mapping to `rag_kb_ingestion_configs` table with FK to `rag_knowledge_bases`
- [x] 2.2 Add `SqlAlchemyIngestionConfigRepository` in `apps/api/app/infrastructure/rag_catalog.py` implementing `IngestionConfigRepository` protocol
- [x] 2.3 Create Alembic migration `apps/api/alembic/versions/20260808_01_kb_ingestion_config.py` — create `rag_kb_ingestion_configs` table with all threshold columns + `auto_review` boolean

## 3. Backend — Application & API Layer

- [x] 3.1 Add `IngestionConfigService` in `apps/api/app/application/` with `get_config(kb_id, tenant_id)` returning config or defaults, and `upsert_config(kb_id, tenant_id, data)` with validation
- [x] 3.2 Add Pydantic request/response schemas `IngestionConfigRead` and `IngestionConfigWrite` in `apps/api/app/interfaces/http/schemas.py` with field-level validators (ranges: coverage 0.0–1.0, ratio 0.0–1.0, confidence 0.0–1.0)
- [x] 3.3 Add `GET /rag/knowledge-bases/{kb_id}/ingestion-config` endpoint in routes — returns config or defaults, tenant-scoped
- [x] 3.4 Add `PUT /rag/knowledge-bases/{kb_id}/ingestion-config` endpoint in routes — upserts config, returns updated record
- [x] 3.5 Wire `IngestionConfigRepository` into DI container / dependency injection in `apps/api/app/interfaces/http/dependencies.py`

## 4. Backend — Parse Stage Integration

- [x] 4.1 Update parse stage (`apps/api/app/application/rag/stages/parse.py`) to read `IngestionConfig` for the document's KB at job start
- [x] 4.2 Pass config thresholds into `QualityGate` constructor (replacing hardcoded defaults)
- [x] 4.3 After quality gate evaluation, if `auto_review=true`, override routing to `NEEDS_REVIEW` regardless of gate outcome — persist quality evidence before overriding

## 5. Frontend — Shared Schema, Types & Constants

- [x] 5.1 Add `ingestionConfigSchema` and `IngestionConfigWriteSchema` Zod schemas in `packages/schemas/` for form validation (threshold fields + auto_review)
- [x] 5.2 Add `IngestionConfig` response type in `packages/types/` matching `IngestionConfigRead` API shape
- [x] 5.3 Add ingestion config API path constant in `apps/web/constants/`

## 6. Frontend — React Query Hook

- [x] 6.1 Create `apps/web/hooks/transactions/use-ingestion-config/` folder with `use-get-ingestion-config.ts` (useQuery) and `use-upsert-ingestion-config.ts` (useMutation)
- [x] 6.2 Add index barrel `apps/web/hooks/transactions/use-ingestion-config/index.ts`

## 7. Frontend — KB Detail Layout (Tab Shell)

- [x] 7.1 Create `apps/web/app/console/knowledge-bases/[id]/layout.tsx` — fetch KB by id, render KB name + status badge header + tab bar with 4 tabs (Planner, Memory, Decomposition, Ingestion Settings)
- [x] 7.2 Create `apps/web/app/console/knowledge-bases/[id]/kb-detail-layout-content.tsx` — client component handling active tab derived from `usePathname()` and rendering tab navigation
- [x] 7.3 Verify existing sub-routes (`/planner`, `/memory`, `/decomposition`) render correctly inside new layout without changes to their own files

## 8. Frontend — Ingestion Settings Tab

- [x] 8.1 Create `apps/web/app/console/knowledge-bases/[id]/ingestion/page.tsx` — thin Suspense wrapper
- [x] 8.2 Create `apps/web/app/console/knowledge-bases/[id]/ingestion/ingestion-content.tsx` — client component with form (react-hook-form + Zod), threshold number inputs, auto_review toggle with warning label, save button
- [x] 8.3 Wire `use-get-ingestion-config` and `use-upsert-ingestion-config` hooks into `ingestion-content.tsx`

## 9. Frontend — KB List Page Refactor

- [x] 9.1 Update `apps/web/app/console/knowledge-bases/knowledge-bases-content.tsx` — replace per-KB Planner/Memory action buttons with single "Open" button linking to `/{id}/planner`
- [x] 9.2 Ensure KB name or row is also clickable as entry point to KB detail

## 10. Verification

- [x] 10.1 Run `cd apps/api && uv run pytest` — all existing tests pass, quality gate tests cover new invalid char ratio check
- [x] 10.2 Run `cd apps/web && bun run typecheck` — no type errors
- [x] 10.3 Run `cd apps/web && bun run lint` — no Biome errors
- [x] 10.4 Manual smoke test: upload a document with `auto_review=true` KB → confirm it lands in `NEEDS_REVIEW`
- [x] 10.5 Manual smoke test: upload a clean document with `auto_review=false` → confirm it reaches `READY` without review
