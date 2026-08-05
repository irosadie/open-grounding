## Why

User saat ini harus memasukkan UUID knowledge base secara manual di form Ingestion dan Retrieval — tidak ada cara untuk tahu UUID mana yang valid tanpa akses langsung ke database. Ini membuat platform tidak bisa dipakai secara mandiri oleh operator.

## What Changes

- **API**: endpoint CRUD knowledge base (`POST /rag/knowledge-bases`, `GET /rag/knowledge-bases`, `DELETE /rag/knowledge-bases/{id}`)
- **UI Ingestion**: input KB ID diganti dengan dropdown/select yang menampilkan daftar knowledge base aktif milik tenant
- **UI Retrieval**: input tag KB IDs diganti dengan multi-select dari daftar knowledge base yang tersedia
- **UI Console**: tambah halaman `/console/knowledge-bases` untuk manage (create, list, delete) knowledge base

## Capabilities

### New Capabilities
- `knowledge-base-crud`: API dan UI untuk membuat, melihat, dan menghapus knowledge base
- `knowledge-base-selector`: komponen selector untuk memilih KB di form Ingestion dan Retrieval

### Modified Capabilities
- `rag-ingestion-ui`: input KB ID string diganti dengan selector dari daftar KB nyata
- `rag-retrieval-ui`: input tag KB IDs diganti dengan multi-select dari daftar KB nyata

## Impact

- `apps/api/app/` — domain knowledge, use case, repository, route baru untuk KB CRUD
- `apps/web/app/console/` — halaman baru `/console/knowledge-bases`
- `apps/web/app/console/ingestion/` — ganti input KB ID dengan selector
- `apps/web/app/console/retrieval/` — ganti tag input KB IDs dengan multi-select
- `apps/web/hooks/transactions/` — hook baru `use-knowledge-bases`
- `packages/schemas/` — schema baru untuk KB create/list
- `packages/types/` — type baru untuk KB response
- `docs/openapi.json` — regenerate
