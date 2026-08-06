## 1. Database — RetrievalConfig Schema

- [ ] 1.1 Buat ORM model `RetrievalConfigRecord` di `apps/api/app/infrastructure/rag_catalog.py`
- [ ] 1.2 Alembic migration: tabel `rag_retrieval_configs` (1:1 dengan index profile, unique constraint `(tenant_id, index_profile_id)`)
- [ ] 1.3 Kolom: dense_weight, sparse_weight, fusion_k, dense_candidates, sparse_candidates, fused_candidates, enabled, timestamps

## 2. API — Domain & Repository

- [ ] 2.1 Buat domain entity `RetrievalConfig` di `apps/api/app/domain/rag/profiles.py`
- [ ] 2.2 Buat repository interface + `SqlAlchemyRetrievalConfigRepository` (find_by_profile, upsert, delete)

## 3. API — Fusion Engine

- [ ] 3.1 Buat `apps/api/app/application/retrieval_fusion.py` — `rrf_fuse(dense, sparse, k, dense_weight, sparse_weight, cap)`
- [ ] 3.2 Unit tests `tests/test_retrieval_fusion.py` (weights, k, missing band, cap, ties)

## 4. API — Retrieval Service Integration

- [ ] 4.1 Update `rag_hybrid_retrieval.py` — load `RetrievalConfig`, run dense+sparse parallel, fuse via RRF, cap
- [ ] 4.2 Fallback ke defaults jika config tidak ada
- [ ] 4.3 Integration test: dense miss + sparse hit → fused returns chunk

## 5. API — Config Service & Routes

- [ ] 5.1 Buat `retrieval_config_service.py` — get/upsert/delete + validasi bounds
- [ ] 5.2 Tambah DTOs ke `schemas.py`: `RetrievalConfigRequest`, `RetrievalConfigResponse`
- [ ] 5.3 Routes di `index_profile_router`: GET/PUT/DELETE `/rag/index-profiles/{id}/retrieval`
- [ ] 5.4 Tambah DI

## 6. Shared Contracts

- [ ] 6.1 Zod schema `retrievalConfigSchema` di `packages/schemas/retrieval.ts`
- [ ] 6.2 Response type `RetrievalConfigResponse` di `packages/types/retrieval-response.ts`

## 7. Frontend — Hooks & UI

- [ ] 7.1 Route constants + query keys untuk retrieval config
- [ ] 7.2 Hooks di `use-retrieval-config/`: `useRetrievalConfig`, `useUpsertRetrievalConfig`, `useDeleteRetrievalConfig`
- [ ] 7.3 Update halaman index profile settings — section "Retrieval" dengan form dense_weight, sparse_weight, fusion_k, candidates, enabled toggle
- [ ] 7.4 Inline validation errors

## 8. OpenAPI & Verification

- [ ] 8.1 Regenerate `docs/openapi.json`
- [ ] 8.2 Run `bun run typecheck` (web) — no errors
- [ ] 8.3 Run `bun run lint` (web) — no errors
- [ ] 8.4 Run `bun run test` (api) — all pass
- [ ] 8.5 Test end-to-end: set sparse_weight tinggi → query keyword → hasil lexical tampil di evidence
