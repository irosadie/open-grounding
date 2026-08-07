## Context

Pengguna saat ini tidak bisa melampirkan metadata bisnis kustom ke dokumen yang diupload. Payload Qdrant bersifat hardcoded — hanya berisi field sistem seperti `tenant_id`, `classification`, `acl_principals`, dll. Tidak ada channel untuk data organisasi seperti `author`, `department`, atau `source_system`.

Stack yang relevan:
- Intake: `POST /rag/ingestion/intake` → `IngestionIntakeService.create_intake()` → `SqlAlchemyDocumentVersionRepository.create()`
- DB: `rag_document_versions` (PostgreSQL, SQLAlchemy async, Alembic)
- Index: `workers/stages/index.py` → `AsyncQdrantClient.upsert()`
- Domain: `DocumentVersion` frozen dataclass

## Goals / Non-Goals

**Goals:**
- User bisa kirim `metadata: dict[str, str]` di intake request
- Metadata dipersist di `rag_document_versions.metadata_json` (JSONB)
- Metadata di-forward ke setiap Qdrant point payload saat index stage
- Validasi di API layer: max 20 keys, max 256 chars per key/value, string-only values

**Non-Goals:**
- Metadata tidak bisa diupdate setelah intake dibuat
- Tidak ada Qdrant payload index untuk metadata keys (tidak bisa difilter saat retrieval)
- Tidak ada perubahan pada retrieval/search/policy logic
- Tidak ada frontend UI untuk metadata di scope ini
- Tidak ada nested object atau array di metadata

## Decisions

### 1. Simpan di JSONB, bukan kolom terpisah

**Pilihan:** Satu kolom `metadata_json JSONB nullable` di `rag_document_versions`.

**Alasan:** Metadata bersifat arbitrary — tidak ada schema tetap per tenant. JSONB di PostgreSQL efficient untuk read dan cukup untuk kebutuhan ini. Alternatif (kolom terpisah per key) tidak scalable dan membutuhkan DDL change per penambahan field.

### 2. Validasi di Pydantic layer, bukan domain layer

**Pilihan:** Validasi (max keys, max length, string-only) dilakukan di `CreateIntakeRequest` Pydantic model via `@field_validator`.

**Alasan:** Ini adalah constraint input, bukan business rule. Domain layer (`DocumentVersion`) cukup menyimpan `metadata: dict[str, str] | None` tanpa validasi tambahan. Pydantic validator sudah dijalankan sebelum masuk ke service layer.

### 3. Inject metadata ke Qdrant payload as-is, tanpa flattening

**Pilihan:** Simpan metadata sebagai nested dict di payload Qdrant: `payload["metadata"] = {"author": "john", "dept": "legal"}`.

**Alasan:** Tidak perlu difilter saat retrieval (non-goal), jadi tidak perlu di-flatten ke top-level payload keys. Struktur nested lebih mudah di-read di sisi retrieval candidate. Jika di masa depan perlu di-filter, bisa ditambahkan Qdrant payload index secara terpisah.

### 4. Metadata immutable setelah intake

**Pilihan:** Tidak ada update endpoint untuk metadata.

**Alasan:** `DocumentVersion` adalah immutable record — mengikuti pola existing di codebase. Jika metadata perlu berubah, user harus upload dokumen baru (new version). Ini menjaga konsistensi antara DB record dan Qdrant payload.

## Risks / Trade-offs

- **[Risk] Metadata tidak bisa difilter di Qdrant** → Acceptable karena non-goal. Jika dibutuhkan di masa depan, tambahkan `provision_payload_indexes` untuk metadata keys.
- **[Risk] JSONB tidak validate schema di DB level** → Mitigasi: validasi ketat di Pydantic layer sebelum data masuk ke repo.
- **[Risk] Metadata besar bisa memperbesar Qdrant payload size** → Mitigasi: batas 20 keys × 256 chars = max ~5KB per point, masih sangat reasonable.

## Migration Plan

1. Buat Alembic migration: `ALTER TABLE rag_document_versions ADD COLUMN metadata_json JSONB NULL`
2. Deploy API changes (backward compatible — kolom nullable, field optional)
3. Existing document versions tetap berjalan normal dengan `metadata_json = NULL`
4. Rollback: drop kolom (tidak ada data loss karena fitur baru, kolom nullable)

## Open Questions

- Apakah di masa depan metadata perlu di-expose di response `GET /ingestion/documents`? Saat ini tidak di-scope.
- Apakah perlu keyword index di Qdrant untuk metadata keys tertentu yang sudah diketahui (misal `department`)? Bisa jadi task terpisah jika dibutuhkan.
