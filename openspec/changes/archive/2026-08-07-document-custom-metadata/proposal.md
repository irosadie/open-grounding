## Why

Saat ini pengguna tidak bisa melampirkan metadata kustom (seperti `author`, `department`, `tags`, `source_system`) ke dokumen yang diupload. Semua payload di Qdrant bersifat hardcoded dari sistem — tidak ada channel untuk data bisnis dari pengguna. Ini memblokir use case seperti filtering dokumen berdasarkan atribut organisasi, audit trail berbasis metadata, dan personalisasi retrieval.

## What Changes

- `POST /rag/ingestion/intake` menerima field opsional `metadata: dict[str, str]` di request body
- `metadata` disimpan di kolom `metadata_json` (JSONB) di tabel `rag_document_versions`
- Saat index stage, `metadata` di-inject ke Qdrant point payload di bawah key `metadata`
- Metadata disimpan sebagai flat key-value string — tidak ada nested object
- Maksimum 20 key, tiap key dan value maksimum 256 karakter
- Metadata bersifat read-only setelah intake dibuat (tidak ada update endpoint)

## Capabilities

### New Capabilities
- `document-custom-metadata`: Kemampuan pengguna menyertakan flat key-value metadata kustom saat intake dokumen, yang dipersist di DB dan di-forward ke Qdrant point payload.

### Modified Capabilities
- `rag-source-intake-and-versioning`: Intake request kini mendukung field `metadata` opsional dengan validasi batas ukuran.
- `rag-ingestion-orchestration-and-indexing`: Qdrant publication kini menyertakan `metadata` dari `DocumentVersion` sebagai bagian dari mandatory payload.

## Impact

- **API**: `CreateIntakeRequest` (Pydantic) di `interfaces/http/routes.py`
- **Application**: `IngestionIntakeService.create_intake()` di `application/ingestion_intake_service.py`
- **Domain**: `DocumentVersion` dataclass di `domain/rag/catalog.py`
- **Infrastructure**: `DocumentVersionRecord` ORM + `SqlAlchemyDocumentVersionRepository.create()` di `infrastructure/rag_catalog.py`
- **Worker**: `index_chunks()` di `workers/stages/index.py`
- **DB**: Alembic migration baru — tambah kolom `metadata_json JSONB nullable` di `rag_document_versions`
- **Tidak ada perubahan** pada retrieval/search logic, policy filter, atau frontend
