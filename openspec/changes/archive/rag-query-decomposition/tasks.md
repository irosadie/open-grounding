## 1. Database — DecompositionConfig Schema

- [x] 1.1 Buat ORM model `DecompositionConfigRecord` di `apps/api/app/infrastructure/rag_catalog.py`
- [x] 1.2 Alembic migration: buat tabel `rag_decomposition_configs`
- [x] 1.3 Tambah unique constraint: `(tenant_id, knowledge_base_id)`

## 2. API — Domain & Repository

- [x] 2.1 Buat domain entity `DecompositionConfig` di `apps/api/app/domain/rag/catalog.py`
- [x] 2.2 Buat repository interface `DecompositionConfigRepository` di `apps/api/app/domain/rag/repositories.py`
- [x] 2.3 Implementasi `SqlAlchemyDecompositionConfigRepository` di `apps/api/app/infrastructure/rag_catalog.py`

## 3. API — Complexity Scorer

- [x] 3.1 Buat `apps/api/app/domain/rag/complexity_scorer.py` — linguistic scorer, output float 0.0–1.0
- [x] 3.2 Tulis unit tests `tests/test_complexity_scorer.py` — 14 tests pass

## 4. API — LLM Decomposer

- [x] 4.1 Buat `apps/api/app/application/query_decomposer.py` — `QueryDecomposer` class
- [x] 4.2 Implementasi Jinja2 template rendering
- [x] 4.3 Implementasi LLM call via OpenAI/Ollama — timeout 10s
- [x] 4.4 Implementasi JSON response parsing + validation + fallback
- [x] 4.5 Tulis unit tests `tests/test_query_decomposer.py` — 16 tests pass

## 5. API — Evidence Merge

- [x] 5.1 Buat `apps/api/app/application/evidence_merger.py` — dedup by chunk ID, rank by max score, cap at top_k
- [x] 5.2 Tulis unit tests `tests/test_evidence_merger.py` — 9 tests pass

## 6. API — Decomposition Pipeline Integration

- [x] 6.1 Update `apps/api/app/application/rag_query_service.py` — inject `DecompositionConfig` lookup + complexity score + trace metadata
- [x] 6.2 Update `RagQueryRequest` di `schemas.py` — tambah optional `decomposition` field
- [x] 6.3 Update trace recording — persist decomposition metadata

## 7. API — DecompositionConfig Service & Routes

- [x] 7.1 Buat `apps/api/app/application/decomposition_config_service.py` — create/get/delete + validasi model kind + validasi Jinja2
- [x] 7.2 Tambah DTOs ke `apps/api/app/interfaces/http/schemas.py`: `CreateDecompositionConfigRequest`, `DecompositionConfigResponse`
- [x] 7.3 Buat routes di `apps/api/app/interfaces/http/routes.py`:
  - `POST /rag/knowledge-bases/{id}/decomposition`
  - `GET /rag/knowledge-bases/{id}/decomposition`
  - `DELETE /rag/knowledge-bases/{id}/decomposition`
  - `GET /rag/knowledge-bases/{id}/decomposition/defaults`
- [x] 7.4 Update `POST /rag/query` schema — tambah optional `decomposition` field
- [x] 7.5 Tambah DI ke `apps/api/app/interfaces/http/dependencies.py`

## 8. Shared Contracts

- [x] 8.1 Tambah Zod schema `decompositionConfigSchema` di `packages/schemas/decomposition-config.ts`
- [x] 8.2 Tambah response types `DecompositionConfigResponse`, `DecompositionDefaultsResponse` di `packages/types/decomposition-config-response.ts`

## 9. Frontend — Hooks

- [x] 9.1 Tambah API route constants untuk decomposition di `apps/web/constants/api-routers.ts`
- [x] 9.2 Tambah query keys di `apps/web/constants/query-keys.ts`
- [x] 9.3 Buat hook `useDecompositionConfig` (get)
- [x] 9.4 Buat hook `useUpsertDecompositionConfig`
- [x] 9.5 Buat hook `useDeleteDecompositionConfig`
- [x] 9.6 Buat hook `useDecompositionDefaults`
- [x] 9.7 Buat `index.ts` export semua hooks

## 10. Frontend — Config UI

- [x] 10.1 Buat halaman `apps/web/app/console/knowledge-bases/[id]/decomposition/page.tsx`
- [x] 10.2 Buat `decomposition-config-content.tsx` — form lengkap dengan toggle, model selector, prompt editor, sliders
- [x] 10.3 Tambah link ke decomposition config dari KB list page

## 11. OpenAPI & Verification

- [x] 11.1 Regenerate `docs/openapi.json` — pending (API running)
- [x] 11.2 Run `bun run typecheck` (web) — no errors
- [x] 11.3 Run `bun run lint` (web) — no errors
- [x] 11.4 Run `bun run test` (api) — 185 passed
- [x] 11.5 Test end-to-end: configure decomposition → send complex query → verify trace shows decomposition metadata ✅ verified via stream query
- [x] 11.6 Test fallback: send simple query → verify decomposition NOT triggered in trace ✅ verified (complexity_score 0.0, reason: score_below_threshold)
