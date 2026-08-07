## Context

Setelah parse selesai, dokumen masuk `NEEDS_REVIEW` dan pipeline berhenti menunggu approval human. Namun tidak ada signal visual di navigation bahwa ada dokumen yang perlu ditinjau. User harus masuk ke `/console/ingestion` dan memilih KB satu per satu untuk mengetahuinya — ini membuat review gate tidak efektif.

Stack yang relevan:
- Backend: FastAPI + SQLAlchemy async, `rag_document_versions.lifecycle_state`
- Frontend: Next.js App Router, sidebar di `components/console-sidebar/`, nav config di `configs/console.ts`
- Data fetching: react-query dengan polling

## Goals / Non-Goals

**Goals:**
- Endpoint `GET /rag/ingestion/pending-review/count` yang return `{ count: int }`
- Hook `useNeedsReviewCount` dengan polling setiap 30 detik
- Badge merah di menu "Documents" sidebar jika count > 0

**Non-Goals:**
- Tidak ada notifikasi push atau email
- Tidak ada breakdown per KB
- Tidak ada badge di halaman lain selain sidebar
- Tidak ada perubahan pada logic review itu sendiri

## Decisions

### 1. Dedicated count endpoint, bukan derive dari documents list

**Alasan:** `GET /rag/ingestion/documents` butuh `knowledge_base_id` — tidak bisa fetch semua KB sekaligus untuk hitung total. Dedicated count endpoint lebih efisien (single query `COUNT`) dan tidak expose data dokumen yang tidak perlu.

### 2. Polling 30 detik di sidebar

**Alasan:** Sidebar selalu visible — tidak perlu refetch agresif. 30 detik cukup responsive untuk use case review tanpa membebani server.

### 3. Badge di config nav, bukan hardcode di sidebar

**Alasan:** `ConsoleSidebar` sudah loop dari `consoleNavItems` config. Tambah field `badgeCount?: number` ke config item lebih clean daripada hardcode logic khusus untuk "Documents" di sidebar component.

Tapi karena badge count bersifat dynamic (dari API), sidebar harus inject nilai ini — bukan dari static config. Solusi: sidebar fetch count sendiri dan inject ke item "Documents" saat render.

## Risks / Trade-offs

- **[Risk] Polling menambah request ke server** → Mitigasi: interval 30 detik, query ringan (COUNT only)
- **[Risk] Badge tidak update real-time** → Acceptable, 30 detik cukup untuk use case ini

## Migration Plan

Tidak ada migration DB. Perubahan additive — endpoint baru, hook baru, sidebar update minor.
