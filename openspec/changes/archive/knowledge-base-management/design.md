## Context

Saat ini tidak ada endpoint untuk manage knowledge base. Record KB harus dibuat manual lewat SQL. Platform tidak bisa dipakai secara mandiri tanpa akses DB.

Form Ingestion dan Retrieval menggunakan plain text input untuk KB ID — user harus tahu UUID KB yang valid sebelumnya, yang tidak mungkin dilakukan tanpa akses DB langsung.

## Goals / Non-Goals

**Goals:**
- API CRUD KB: create, list (per tenant), delete (soft)
- UI halaman `/console/knowledge-bases` untuk manage KB
- Ganti input KB ID di Ingestion dengan dropdown select
- Ganti tag input KB IDs di Retrieval dengan multi-select
- KB selector reusable untuk kedua form

**Non-Goals:**
- Edit/rename KB (bisa ditambah phase berikutnya)
- KB settings (embedding profile, index config)
- Connector management
- Pagination KB list (scope awal simple, jumlah KB per tenant sedikit)

## Decisions

### 1. Slug sebagai identifier user-facing
KB punya `slug` (kebab-case, unik per tenant) yang ditampilkan di UI. UUID dipakai internal. User membuat KB dengan nama + slug, tidak perlu tahu UUID.

### 2. Selector load on mount
KB list di-fetch saat form dibuka (`useQuery`). Tidak ada lazy load atau search — jumlah KB per tenant diasumsikan < 50 untuk v1.

### 3. Soft delete
DELETE endpoint set status ke `ARCHIVED`, tidak hapus data. Dokumen yang sudah diingestion tetap ada.

### 4. Single reusable selector component
Buat komponen `KnowledgeBaseSelect` (single) dan `KnowledgeBaseMultiSelect` (multi) yang keduanya consume hook `useKnowledgeBases`. Dipakai di Ingestion dan Retrieval.

### 5. API mengikuti Clean Architecture existing
Entity → Use Case → Repository → Controller → Route. Tidak ada shortcut.

## Risks / Trade-offs

- **KB list kosong saat pertama** → UI harus tampilkan empty state dengan CTA "Create your first knowledge base"
- **Selector disabled saat loading** → indicator loading di selector
- **Delete KB yang masih ada dokumen** → soft delete, dokumen tetap ada tapi KB tidak bisa dipilih lagi di form baru

## Migration Plan

1. Implement API KB CRUD (entity → use case → repo → route)
2. Regenerate OpenAPI
3. Tambah shared schema + types
4. Implement hook `use-knowledge-bases`
5. Implement selector components
6. Update Ingestion page — ganti input dengan selector
7. Update Retrieval page — ganti tag input dengan multi-select
8. Tambah halaman `/console/knowledge-bases`
9. Update console nav items

## Open Questions

- Apakah slug bisa diedit setelah KB dibuat? → **Tidak untuk v1**
- Apakah perlu konfirmasi sebelum delete KB yang punya dokumen? → **Ya, tampilkan jumlah dokumen**
