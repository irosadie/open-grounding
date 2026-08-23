## Why

Setelah dokumen melewati tahap parsing/OCR, hasilnya perlu diverifikasi oleh manusia sebelum dilanjutkan ke chunking dan indexing. Saat ini tidak ada UI untuk melihat, mengedit, menyetujui, atau menolak teks hasil parsing tersebut. Dokumen dengan state `NEEDS_REVIEW` terjebak tanpa jalur tindakan dari frontend.

## What Changes

- Buat halaman review di `apps/web/app/console/ingestion/review/[versionId]/` yang memungkinkan user:
  1. Melihat teks hasil parsing (dari `GET /rag/ingestion/{version_id}/parsed-text`)
  2. Mengedit teks inline dengan Tiptap editor
  3. Submit teks terkoreksi (`PATCH /rag/ingestion/{version_id}/parsed-text`)
  4. Approve dokumen → trigger chunking (`POST /rag/ingestion/{version_id}/approve`)
  5. Reject dokumen → set FAILED (`POST /rag/ingestion/{version_id}/reject`)
- Tampilkan metadata dokumen: filename, KB name, state, uploaded at
- Tampilkan warning banner jika state adalah `NEEDS_REVIEW`
- Setelah approve/reject, redirect kembali ke halaman ingestion list

## Capabilities

### New Capabilities

- `ingestion-review-ui`: Halaman review teks parsing dengan editor inline, aksi approve/reject, metadata dokumen, dan warning banner untuk state `NEEDS_REVIEW`

### Modified Capabilities

- `rag-ingestion-response` (types): tambah tipe `ParsedTextResponse`, `ApproveIngestionResponse`, `RejectIngestionResponse`
- `rag-ingestion` (schemas): tambah schema `submitParsedTextSchema`, state `NEEDS_REVIEW` ke `documentVersionLifecycleStates`
- `use-rag-ingestion` (hooks): tambah hook `useIngestionParsedText`, `useSubmitParsedText`, `useApproveIngestion`, `useRejectIngestion`

## Impact

- `packages/types/rag-ingestion-response.ts` — tambah tipe response baru
- `packages/schemas/rag-ingestion.ts` — tambah state `NEEDS_REVIEW`, tambah `submitParsedTextSchema`
- `apps/web/hooks/transactions/use-rag-ingestion/` — tambah 4 hook baru
- `apps/web/app/console/ingestion/review/[versionId]/page.tsx` — halaman baru (thin Suspense wrapper)
- `apps/web/app/console/ingestion/review/[versionId]/review-content.tsx` — Client Component orchestrator
- `apps/web/app/console/ingestion/review/[versionId]/_components/` — komponen private route

## Dependencies

- **parsed-text-persistence** — API endpoints `GET /rag/ingestion/{version_id}/parsed-text`, `PATCH /rag/ingestion/{version_id}/parsed-text`, `POST /rag/ingestion/{version_id}/approve`, `POST /rag/ingestion/{version_id}/reject` harus tersedia sebelum integrasi
