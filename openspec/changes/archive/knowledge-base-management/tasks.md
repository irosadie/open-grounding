## 1. API — Entity & Repository

- [x] 1.1 Buat entity `KnowledgeBase` di `apps/api/app/domain/knowledge/` — ada di `domain/rag/catalog.py`
- [x] 1.2 Buat repository interface `KnowledgeBaseRepository` di `apps/api/app/domain/knowledge/` — ada di `domain/rag/repositories.py`
- [x] 1.3 Buat SQLAlchemy repository implementation di `apps/api/app/infrastructure/postgres/` — ada di `infrastructure/rag_catalog.py`

## 2. API — Use Cases

- [x] 2.1 Buat use case `CreateKnowledgeBase` di `apps/api/app/application/` — ada di `application/knowledge_base_service.py`
- [x] 2.2 Buat use case `ListKnowledgeBases` di `apps/api/app/application/` — ada di `application/knowledge_base_service.py`
- [x] 2.3 Buat use case `DeleteKnowledgeBase` di `apps/api/app/application/` — ada di `application/knowledge_base_service.py`

## 3. API — HTTP Interface

- [x] 3.1 Buat Pydantic DTOs (request + response) di `apps/api/app/interfaces/http/schemas.py`
- [x] 3.2 Buat controller `KnowledgeBaseController` di `apps/api/app/interfaces/http/` — via `kb_router`
- [x] 3.3 Buat route `POST /rag/knowledge-bases`
- [x] 3.4 Buat route `GET /rag/knowledge-bases`
- [x] 3.5 Buat route `DELETE /rag/knowledge-bases/{id}`
- [x] 3.6 Tambah dependency injection KB use cases di `apps/api/app/main.py` atau DI container
- [x] 3.7 Regenerate `docs/openapi.json`

## 4. Shared Contracts

- [x] 4.1 Tambah Zod schema `knowledgeBaseCreateSchema` di `packages/schemas/`
- [x] 4.2 Tambah response type `KnowledgeBaseResponse` dan `KnowledgeBaseListResponse` di `packages/types/`

## 5. Frontend — Hooks

- [x] 5.1 Tambah API route constants untuk KB di `apps/web/constants/api-routers.ts`
- [x] 5.2 Tambah query keys untuk KB di `apps/web/constants/query-keys.ts`
- [x] 5.3 Buat hook `useKnowledgeBases` (list) di `apps/web/hooks/transactions/use-knowledge-bases/`
- [x] 5.4 Buat hook `useCreateKnowledgeBase` di `apps/web/hooks/transactions/use-knowledge-bases/`
- [x] 5.5 Buat hook `useDeleteKnowledgeBase` di `apps/web/hooks/transactions/use-knowledge-bases/`
- [x] 5.6 Buat `index.ts` untuk export semua hooks

## 6. Frontend — Selector Components

- [x] 6.1 Buat komponen `KnowledgeBaseSelect` (single) di `apps/web/components/knowledge-base-select/`
- [x] 6.2 Buat komponen `KnowledgeBaseMultiSelect` di `apps/web/components/knowledge-base-multi-select/`

## 7. Frontend — Update Pages

- [x] 7.1 Update `apps/web/app/console/ingestion/ingestion-content.tsx` — ganti input KB ID dengan `KnowledgeBaseSelect`
- [x] 7.2 Update `apps/web/app/console/retrieval/retrieval-content.tsx` — ganti tag input dengan `KnowledgeBaseMultiSelect`

## 8. Frontend — Knowledge Base Management Page

- [x] 8.1 Buat halaman `apps/web/app/console/knowledge-bases/page.tsx`
- [x] 8.2 Buat `knowledge-bases-content.tsx` dengan list KB + create form + delete action
- [x] 8.3 Tambah nav item `Knowledge Bases` di `apps/web/configs/console.ts`

## 9. Verification

- [x] 9.1 Run `bun run typecheck` (web) — no errors
- [x] 9.2 Run `bun run lint` (web) — no errors
- [x] 9.3 Run `bun run test` (api) — all pass
- [x] 9.4 Test end-to-end: create KB → ingestion dengan selector → retrieval dengan multi-select
