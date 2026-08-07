## 1. Shared Schemas (`packages/schemas/`)

- [x] 1.1 Tambah state `NEEDS_REVIEW` ke array `documentVersionLifecycleStates` di `rag-ingestion.ts`
- [x] 1.2 Tambah `submitParsedTextSchema` dan export tipe `SubmitParsedTextProps` di `rag-ingestion.ts`
- [x] 1.3 Pastikan `index.ts` di `packages/schemas/` sudah re-export semua export baru

## 2. Shared Types (`packages/types/`)

- [x] 2.1 Tambah tipe `ParsedTextResponse` ke `rag-ingestion-response.ts`
- [x] 2.2 Tambah tipe `ApproveIngestionResponse` ke `rag-ingestion-response.ts`
- [x] 2.3 Tambah tipe `RejectIngestionResponse` ke `rag-ingestion-response.ts`
- [x] 2.4 Pastikan `index.ts` di `packages/types/` sudah re-export semua tipe baru

## 3. Hooks (`apps/web/hooks/transactions/use-rag-ingestion/`)

- [x] 3.1 Buat `use-parsed-text.ts` — `useIngestionParsedText(versionId: string)` dengan `useQuery`
- [x] 3.2 Buat `use-submit-parsed-text.ts` — `useSubmitParsedText(versionId: string)` dengan `useMutation`
- [x] 3.3 Buat `use-approve-ingestion.ts` — `useApproveIngestion(versionId: string)` dengan `useMutation`
- [x] 3.4 Buat `use-reject-ingestion.ts` — `useRejectIngestion(versionId: string)` dengan `useMutation`
- [x] 3.5 Export semua hook baru dari `index.ts` di folder `use-rag-ingestion/`

## 4. Private Components (`_components/`)

- [x] 4.1 Buat `_components/document-meta-card.tsx` — card metadata dokumen (filename, KB name, state badge, uploadedAt)
- [x] 4.2 Buat `_components/needs-review-banner.tsx` — banner amber, hanya render jika `lifecycleState === "NEEDS_REVIEW"`
- [x] 4.3 Buat `_components/parsed-text-editor.tsx` — Tiptap editor dengan prop `content`, `editable`, `onChange`
- [x] 4.4 Buat `_components/review-action-bar.tsx` — bar dengan tombol Simpan Koreksi, Approve, dan Tolak (dengan inline confirm untuk Tolak)

## 5. Route Page

- [x] 5.1 Buat `review-content.tsx` — Client Component orchestrator: fetch data, kelola state `editedText` dan `isDirty`, pass props ke `_components/`
- [x] 5.2 Buat `page.tsx` — thin Suspense wrapper yang merender `ReviewContent` dengan `versionId` dari params
- [x] 5.3 Pastikan redirect ke `/console/ingestion` setelah approve/reject berhasil

## 6. Verifikasi

- [x] 6.1 Typecheck pass (`bun run typecheck` di root atau `apps/web`)
- [x] 6.2 Halaman `/console/ingestion/review/[versionId]` dapat diakses tanpa runtime error
- [x] 6.3 Fetch parsed text tampil di editor, metadata card, dan banner muncul sesuai state
- [x] 6.4 Approve berhasil redirect ke `/console/ingestion`
- [x] 6.5 Reject hanya berjalan setelah konfirmasi inline, berhasil redirect ke `/console/ingestion`
- [x] 6.6 Tombol "Simpan Koreksi" disabled saat tidak dirty, aktif setelah teks diedit
- [x] 6.7 Tidak ada import `axios` atau `fetch` langsung di `review-content.tsx` atau `_components/`
- [x] 6.8 Biome lint pass — tidak ada `any`, `console.*`, unused imports, atau semicolons
