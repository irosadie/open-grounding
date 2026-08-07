## Why

Setelah dokumen selesai di-parse, pipeline berhenti di state `NEEDS_REVIEW` dan menunggu approval dari human. Namun tidak ada indikator di sidebar bahwa ada dokumen yang butuh ditinjau — user harus masuk ke halaman `/console/ingestion` dan pilih KB satu per satu untuk mengetahuinya. Ini membuat review gate tidak efektif karena dokumen bisa tertahan lama tanpa diketahui.

## What Changes

- Tambah endpoint `GET /rag/ingestion/pending-review/count` yang return jumlah dokumen `NEEDS_REVIEW` untuk tenant aktif
- Tambah hook `useNeedsReviewCount` di frontend yang fetch count tersebut
- Sidebar menu "Documents" menampilkan badge merah dengan angka jika ada dokumen `NEEDS_REVIEW`

## Capabilities

### New Capabilities
- `ingestion-review-badge`: Badge counter di sidebar menu Documents yang menunjukkan jumlah dokumen yang menunggu review.

### Modified Capabilities
- `rag-source-intake-and-versioning`: API kini expose endpoint count untuk dokumen dalam state `NEEDS_REVIEW`.
- `ingestion-review-ui`: Sidebar navigation kini menampilkan badge counter untuk dokumen pending review.

## Impact

- **API**: Tambah route `GET /rag/ingestion/pending-review/count` di `interfaces/http/routes.py`
- **Infrastructure**: Tambah method `count_needs_review()` di `SqlAlchemyDocumentVersionRepository`
- **Frontend hook**: Tambah `use-needs-review-count.ts` di `hooks/transactions/use-rag-ingestion/`
- **Frontend config**: Update `ConsoleNavItem` type untuk support optional `badge?: number`
- **Frontend sidebar**: Update `ConsoleSidebar` untuk render badge jika ada
