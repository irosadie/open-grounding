# Design: Ingestion Review UI

## Overview

Halaman review memungkinkan operator/user melihat dan mengoreksi teks hasil OCR/parsing sebelum dokumen dilanjutkan ke tahap chunking. Ini adalah "quality gate" manual dalam pipeline ingestion.

Flow utama:
1. User membuka halaman review via link dari ingestion list (atau langsung dari URL)
2. Sistem fetch metadata dokumen + teks parsed via `GET /rag/ingestion/{versionId}/parsed-text`
3. User membaca teks, mengedit jika ada kesalahan OCR, lalu approve atau reject
4. Approve → `PATCH` teks terkoreksi → `POST /approve` → redirect ke ingestion list
5. Reject → `POST /reject` → redirect ke ingestion list

## Route Structure

```
apps/web/app/console/ingestion/review/[versionId]/
├── page.tsx                        ← thin server component, Suspense wrapper
├── review-content.tsx              ← "use client", route orchestrator
└── _components/
    ├── document-meta-card.tsx      ← metadata dokumen (filename, KB, state, uploaded at)
    ├── needs-review-banner.tsx     ← warning banner untuk state NEEDS_REVIEW
    ├── parsed-text-editor.tsx      ← Tiptap editor untuk teks parsed
    └── review-action-bar.tsx       ← tombol Approve dan Reject dengan confirm dialog
```

## Data Flow

```
review-content.tsx
  └→ useIngestionParsedText(versionId)   ← GET parsed text + metadata
  └→ useSubmitParsedText(versionId)      ← PATCH corrected text
  └→ useApproveIngestion(versionId)      ← POST approve
  └→ useRejectIngestion(versionId)       ← POST reject
```

## State Management

`review-content.tsx` mengelola:
- `editedText: string` — teks yang sedang diedit (init dari response API)
- `isDirty: boolean` — true jika teks sudah diedit (dipakai untuk enable tombol "Simpan Koreksi")
- Loading/error state dari masing-masing hook

Tidak perlu form library (react-hook-form) karena ini bukan form multi-field — hanya satu textarea/editor besar.

## Packages Changes

### `packages/schemas/rag-ingestion.ts`

Tambah state `NEEDS_REVIEW` ke array `documentVersionLifecycleStates`:
```ts
export const documentVersionLifecycleStates = [
  "PENDING", "STORED", "PARSING", "NORMALIZING",
  "NEEDS_REVIEW",   // ← baru
  "CHUNKING", "EMBEDDING", "INDEXING",
  "READY", "FAILED", "DELETING",
] as const
```

Tambah schema untuk submit teks terkoreksi:
```ts
export const submitParsedTextSchema = z.object({
  text: z.string().min(1, "Teks tidak boleh kosong"),
})
export type SubmitParsedTextProps = z.infer<typeof submitParsedTextSchema>
```

### `packages/types/rag-ingestion-response.ts`

```ts
export type ParsedTextResponse = {
  versionId: string
  text: string
  filename: string
  knowledgeBaseName: string
  lifecycleState: string
  uploadedAt: string        // ISO 8601
}

export type ApproveIngestionResponse = {
  versionId: string
  lifecycleState: string
}

export type RejectIngestionResponse = {
  versionId: string
  lifecycleState: string
}
```

## Hooks

Semua hook masuk ke folder yang sudah ada `apps/web/hooks/transactions/use-rag-ingestion/`:

| File | Hook | Method |
|---|---|---|
| `use-parsed-text.ts` | `useIngestionParsedText(versionId)` | `useQuery` |
| `use-submit-parsed-text.ts` | `useSubmitParsedText(versionId)` | `useMutation` |
| `use-approve-ingestion.ts` | `useApproveIngestion(versionId)` | `useMutation` |
| `use-reject-ingestion.ts` | `useRejectIngestion(versionId)` | `useMutation` |

## UI Components

### `document-meta-card.tsx`

Panel card menampilkan:
- Filename (bold)
- Knowledge Base name
- State badge (pakai `lifecycleBadgeClass` pattern dari ingestion-content.tsx)
- Uploaded at (format: tanggal lokal Indonesia)

### `needs-review-banner.tsx`

Banner kuning/amber, hanya render jika `lifecycleState === "NEEDS_REVIEW"`:
```
⚠ Dokumen ini membutuhkan tinjauan manual. Periksa teks hasil parsing di bawah, 
  koreksi jika ada kesalahan OCR, lalu Approve atau Reject.
```

### `parsed-text-editor.tsx`

Tiptap editor sederhana (plain text, tanpa rich text formatting):
- Gunakan `@tiptap/react` + `@tiptap/starter-kit` (sudah tersedia di project)
- `editable` prop: `true` selama belum di-approve/reject, `false` setelah terminal action
- Emit `onChange(text: string)` ke parent

### `review-action-bar.tsx`

Sticky bottom bar dengan 3 tombol:
1. **Simpan Koreksi** — disabled jika tidak dirty, trigger `useSubmitParsedText`
2. **Approve** — intent `primary`, trigger `useApproveIngestion` lalu redirect
3. **Tolak** — intent `danger`, konfirmasi dulu (inline confirm state, tanpa modal), trigger `useRejectIngestion` lalu redirect

## Navigation

Setelah approve atau reject berhasil: `router.push("/console/ingestion")`

Tombol "Kembali" di atas halaman: `router.back()` atau link ke `/console/ingestion`

## Visual Layout

```
┌─────────────────────────────────────────────────┐
│ ← Kembali ke Ingestion                          │
│                                                 │
│ [⚠ Banner NEEDS_REVIEW — jika applicable]       │
│                                                 │
│ ┌─ Metadata Dokumen ──────────────────────────┐ │
│ │ Filename: laporan-q1.pdf                    │ │
│ │ Knowledge Base: KB Keuangan                 │ │
│ │ State: [NEEDS_REVIEW]  Upload: 7 Agt 2026   │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌─ Teks Hasil Parsing ────────────────────────┐ │
│ │                                             │ │
│ │  [Tiptap editor — editable]                 │ │
│ │                                             │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌─ Action Bar (sticky bottom) ────────────────┐ │
│ │  [Simpan Koreksi]  [Approve]  [Tolak]       │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Out of Scope

- History/diff teks sebelum dan sesudah koreksi
- Multi-user concurrent editing
- Auto-save / draft
- Rich text formatting (bold, heading, dll) di editor
- Pagination teks panjang
