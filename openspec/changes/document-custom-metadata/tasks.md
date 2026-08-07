## 1. Database Migration

- [x] 1.1 Buat Alembic migration baru: tambah kolom `metadata_json JSONB NULL` di tabel `rag_document_versions`
- [x] 1.2 Verifikasi migration `upgrade` dan `downgrade` berjalan tanpa error di local

## 2. Domain Layer

- [x] 2.1 Tambah field `metadata: dict[str, str] | None` di frozen dataclass `DocumentVersion` di `apps/api/app/domain/rag/catalog.py`

## 3. Infrastructure Layer

- [x] 3.1 Tambah `metadata_json: Mapped[dict | None]` di `DocumentVersionRecord` ORM di `apps/api/app/infrastructure/rag_catalog.py`
- [x] 3.2 Update method `SqlAlchemyDocumentVersionRepository.create()` untuk menerima dan menyimpan param `metadata`
- [x] 3.3 Update mapping dari `DocumentVersionRecord` ke `DocumentVersion` domain object untuk include `metadata`

## 4. Application Layer

- [x] 4.1 Tambah param `metadata: dict[str, str] | None = None` di `IngestionIntakeService.create_intake()` di `apps/api/app/application/ingestion_intake_service.py`
- [x] 4.2 Pass `metadata` ke `_version_repo.create()` di dalam `create_intake()`

## 5. API Layer

- [x] 5.1 Tambah field `metadata: dict[str, str] | None = None` di `CreateIntakeRequest` Pydantic model di `apps/api/app/interfaces/http/routes.py`
- [x] 5.2 Tambah `@field_validator("metadata")` untuk validasi: max 20 keys, max 256 chars per key dan value, string-only values
- [x] 5.3 Pass `metadata=payload.metadata` ke `service.create_intake()` di route handler `create_intake`

## 6. Worker — Index Stage

- [x] 6.1 Update `index_chunks()` di `apps/api/app/workers/stages/index.py` untuk inject `version.metadata` ke Qdrant point payload jika tidak None

## 7. Tests

- [x] 7.1 Tambah test case di `tests/test_ingestion_routes.py`: intake dengan metadata valid → 201
- [x] 7.2 Tambah test case: intake dengan metadata > 20 keys → 422
- [x] 7.3 Tambah test case: intake dengan value bukan string → 422
- [x] 7.4 Tambah test case: intake dengan key/value > 256 chars → 422
- [x] 7.5 Tambah test case di `tests/test_ingestion_e2e.py`: metadata dipersist di `DocumentVersion` setelah intake
- [x] 7.6 Verifikasi test suite existing tidak ada yang break: `cd apps/api && pytest`
