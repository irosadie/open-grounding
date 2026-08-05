## 1. API — Entity & Repository

- [ ] 1.1 Buat entity `KnowledgeBase` di `apps/api/app/domain/knowledge/`
- [ ] 1.2 Buat repository interface `KnowledgeBaseRepository` di `apps/api/app/domain/knowledge/`
- [ ] 1.3 Buat SQLAlchemy repository implementation di `apps/api/app/infrastructure/postgres/`

## 2. API — Use Cases

- [ ] 2.1 Buat use case `CreateKnowledgeBase` di `apps/api/app/application/`
- [ ] 2.2 Buat use case `ListKnowledgeBases` di `apps/api/app/application/`
- [ ] 2.3 Buat use case `DeleteKnowledgeBase` di `apps/api/app/application/`

## 3. API — HTTP Interface

- [ ] 3.1 Buat Pydantic DTOs (request + response) di `apps/api/app/interfaces/http/schemas.py`
- [ ] 3.2 Buat controller `KnowledgeBaseController` di `apps/api/app/interfaces/http/`
- [ ] 3.3 Buat route `POST /rag/knowledge-bases`
- [ ] 3.4 Buat route `GET /rag/knowledge-bases`
- [ ] 3.5 Buat route `DELETE /rag/knowledge-bases/{id}`
- [ ] 3.6 Tambah dependency injection KB use cases di `apps/api/app/main.py` atau DI container
- [ ] 3.7 Regenerate `docs/openapi.json`

## 4. Shared Contracts

- [ ] 4.1 Tambah Zod schema `knowledgeBaseCreateSchema` di `packages/schemas/`
- [ ] 4.2 Tambah response type `KnowledgeBaseResponse` dan `KnowledgeBaseListResponse` di `packages/types/`

## 5. Frontend — Hooks

- [ ] 5.1 Tambah API route constants untuk KB di `apps/web/constants/api-routers.ts`
- [ ] 5.2 Tambah query keys untuk KB di `apps/web/constants/query-keys.ts`
- [ ] 5.3 Buat hook `useKnowledgeBases` (list) di `apps/web/hooks/transactions/use-knowledge-bases/`
- [ ] 5.4 Buat hook `useCreateKnowledgeBase` di `apps/web/hooks/transactions/use-knowledge-bases/`
- [ ] 5.5 Buat hook `useDeleteKnowledgeBase` di `apps/web/hooks/transactions/use-knowledge-bases/`
- [ ] 5.6 Buat `index.ts` untuk export semua hooks

## 6. Frontend — Selector Components

- [ ] 6.1 Buat komponen `KnowledgeBaseSelect` (single) di `apps/web/components/knowledge-base-select/`
- [ ] 6.2 Buat komponen `KnowledgeBaseMultiSelect` di `apps/web/components/knowledge-base-multi-select/`

## 7. Frontend — Update Pages

- [ ] 7.1 Update `apps/web/app/console/ingestion/ingestion-content.tsx` — ganti input KB ID dengan `KnowledgeBaseSelect`
- [ ] 7.2 Update `apps/web/app/console/retrieval/retrieval-content.tsx` — ganti tag input dengan `KnowledgeBaseMultiSelect`

## 8. Frontend — Knowledge Base Management Page

- [ ] 8.1 Buat halaman `apps/web/app/console/knowledge-bases/page.tsx`
- [ ] 8.2 Buat `knowledge-bases-content.tsx` dengan list KB + create form + delete action
- [ ] 8.3 Tambah nav item `Knowledge Bases` di `apps/web/configs/console.ts`

## 9. Verification

- [ ] 9.1 Run `bun run typecheck` (web) — no errors
- [ ] 9.2 Run `bun run lint` (web) — no errors
- [ ] 9.3 Run `bun run test` (api) — all pass
- [ ] 9.4 Test end-to-end: create KB → ingestion dengan selector → retrieval dengan multi-select
