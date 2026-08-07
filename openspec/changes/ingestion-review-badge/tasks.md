## 1. Backend — Repository

- [ ] 1.1 Tambah method `count_needs_review(*, tenant_id: str) -> int` di `SqlAlchemyDocumentVersionRepository` di `apps/api/app/infrastructure/rag_catalog.py`

## 2. Backend — API Route

- [ ] 2.1 Tambah route `GET /rag/ingestion/pending-review/count` di `apps/api/app/interfaces/http/routes.py` — return `{"count": int}`
- [ ] 2.2 Route harus menggunakan `TenantContextDependency` dan `IngestionServiceDependency`

## 3. Backend — Service

- [ ] 3.1 Tambah method `get_pending_review_count(*, tenant: TenantContext) -> int` di `IngestionIntakeService` di `apps/api/app/application/ingestion_intake_service.py`

## 4. Frontend — Constants

- [ ] 4.1 Tambah `pendingReviewCount` ke `apiRouters.rag.ingestion` di constants

## 5. Frontend — Hook

- [ ] 5.1 Buat `use-needs-review-count.ts` di `apps/web/hooks/transactions/use-rag-ingestion/` dengan `useQuery` dan `refetchInterval: 30_000`
- [ ] 5.2 Export hook dari `index.ts` di folder `use-rag-ingestion/`

## 6. Frontend — Sidebar

- [ ] 6.1 Update `ConsoleSidebar` untuk fetch `useNeedsReviewCount` dan inject badge ke item "Documents"
- [ ] 6.2 Render badge merah dengan angka di sebelah label "Documents" jika count > 0

## 7. Tests

- [ ] 7.1 Tambah test `GET /rag/ingestion/pending-review/count` requires auth → 401
- [ ] 7.2 Run `cd apps/api && pytest` dan pastikan semua tests pass
- [ ] 7.3 Run `cd apps/web && bun run typecheck` dan pastikan clean
