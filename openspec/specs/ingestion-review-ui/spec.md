# ingestion-review-ui Specification

## Purpose
TBD - created by archiving change ingestion-review-ui. Update Purpose after archive.
## Requirements
### Requirement: Fetch Parsed Text

Halaman review SHALL mengambil teks hasil parsing dan metadata dokumen dari endpoint `GET /rag/ingestion/{versionId}/parsed-text` saat pertama kali dimuat.

#### Scenario: Load berhasil

Diberikan `versionId` yang valid dan endpoint tersedia, ketika halaman dimuat, maka teks parsed dan metadata dokumen (filename, KB name, state, uploadedAt) MUST ditampilkan di halaman.

#### Scenario: Load gagal

Diberikan `versionId` yang tidak valid atau endpoint mengembalikan error, ketika halaman dimuat, maka halaman MUST menampilkan pesan error yang informatif dan tombol retry.

#### Scenario: Loading state

Diberikan halaman baru dimuat, ketika data belum tersedia, maka halaman MUST menampilkan skeleton loader atau indikator loading.

---

### Requirement: Tampilkan Metadata Dokumen

Halaman review SHALL menampilkan card metadata dokumen berisi: filename, nama knowledge base, lifecycleState (sebagai badge), dan waktu upload (uploadedAt).

#### Scenario: Metadata lengkap ditampilkan

Diberikan response API berisi semua field metadata, ketika halaman tampil, maka filename, KB name, state badge, dan uploadedAt MUST terlihat di metadata card.

#### Scenario: Badge state sesuai warna

Diberikan `lifecycleState` adalah `NEEDS_REVIEW`, ketika badge ditampilkan, maka badge MUST menggunakan warna amber/warning yang berbeda dari state terminal (READY = hijau, FAILED = merah).

---

### Requirement: Warning Banner NEEDS_REVIEW

Halaman review SHALL menampilkan warning banner kuning/amber jika dan hanya jika `lifecycleState` dokumen adalah `NEEDS_REVIEW`.

#### Scenario: Banner muncul saat NEEDS_REVIEW

Diberikan `lifecycleState === "NEEDS_REVIEW"`, ketika halaman ditampilkan, maka banner peringatan MUST tampil di atas editor dengan teks yang menginstruksikan user untuk memeriksa dan mengoreksi teks.

#### Scenario: Banner tidak muncul untuk state lain

Diberikan `lifecycleState` bukan `NEEDS_REVIEW` (misal `PARSING` atau `READY`), ketika halaman ditampilkan, maka banner peringatan MUST NOT ditampilkan.

---

### Requirement: Editor Teks Parsed

Halaman review SHALL menyediakan editor inline (Tiptap) yang dapat digunakan untuk membaca dan mengedit teks hasil parsing.

#### Scenario: Teks awal dimuat ke editor

Diberikan fetch berhasil dan `text` tersedia di response, ketika editor dirender, maka teks dari API MUST menjadi konten awal editor.

#### Scenario: User mengedit teks

Diberikan editor dalam state editable, ketika user mengubah teks, maka perubahan MUST tercermin di state `editedText` di parent component dan `isDirty` MUST menjadi `true`.

#### Scenario: Editor read-only setelah aksi terminal

Diberikan user sudah melakukan approve atau reject, ketika halaman masih tampil (sebelum redirect selesai), maka editor MUST dalam state `editable={false}`.

---

### Requirement: Simpan Koreksi Teks

Halaman review SHALL menyediakan tombol "Simpan Koreksi" yang mengirimkan teks terkoreksi via `PATCH /rag/ingestion/{versionId}/parsed-text`.

#### Scenario: Tombol disabled saat tidak ada perubahan

Diberikan user belum mengedit teks (isDirty = false), maka tombol "Simpan Koreksi" MUST dalam state disabled.

#### Scenario: Simpan berhasil

Diberikan user sudah mengedit teks dan menekan "Simpan Koreksi", ketika PATCH request berhasil, maka `isDirty` MUST direset ke `false` dan tombol kembali disabled.

#### Scenario: Simpan gagal

Diberikan PATCH request gagal, ketika response error diterima, maka pesan error MUST ditampilkan kepada user tanpa navigasi.

---

### Requirement: Approve Dokumen

Halaman review SHALL menyediakan tombol "Approve" yang memanggil `POST /rag/ingestion/{versionId}/approve` untuk memicu proses chunking.

#### Scenario: Approve berhasil

Diberikan user menekan tombol "Approve" dan POST request berhasil, maka halaman MUST melakukan redirect ke `/console/ingestion`.

#### Scenario: Approve gagal

Diberikan POST request gagal, maka pesan error MUST ditampilkan dan halaman tidak redirect.

#### Scenario: Approve tidak bisa dilakukan saat loading

Diberikan ada request yang sedang berjalan (isPending), maka tombol "Approve" MUST dalam state loading/disabled.

---

### Requirement: Reject Dokumen

Halaman review SHALL menyediakan tombol "Tolak" yang memanggil `POST /rag/ingestion/{versionId}/reject` untuk mengubah state dokumen menjadi FAILED.

#### Scenario: Konfirmasi sebelum reject

Diberikan user menekan tombol "Tolak", maka MUST ada mekanisme konfirmasi inline (bukan modal terpisah) sebelum request dikirim.

#### Scenario: Reject berhasil

Diberikan user mengkonfirmasi reject dan POST request berhasil, maka halaman MUST melakukan redirect ke `/console/ingestion`.

#### Scenario: Reject dibatalkan

Diberikan user menekan "Tolak" lalu membatalkan konfirmasi, maka request MUST NOT dikirim dan halaman tetap di state semula.

#### Scenario: Reject gagal

Diberikan POST request gagal, maka pesan error MUST ditampilkan dan halaman tidak redirect.

---

### Requirement: Navigasi Kembali

Halaman review SHALL menyediakan tautan/tombol untuk kembali ke halaman daftar ingestion.

#### Scenario: Tombol kembali tersedia

Diberikan halaman review ditampilkan, maka MUST ada elemen navigasi di bagian atas halaman yang mengarah ke `/console/ingestion`.

---

### Requirement: Shared Schemas dan Types

Schema `submitParsedTextSchema` dan tipe `ParsedTextResponse`, `ApproveIngestionResponse`, `RejectIngestionResponse` SHALL didefinisikan di package shared sesuai arsitektur monorepo.

#### Scenario: Schema validasi teks submit

Diberikan `submitParsedTextSchema` digunakan untuk validasi, ketika `text` kosong, maka validasi MUST gagal dengan pesan error.

#### Scenario: State NEEDS_REVIEW ada di enum shared

Diberikan `documentVersionLifecycleStates` digunakan di FE maupun BE, maka state `NEEDS_REVIEW` MUST terdaftar di array enum shared di `packages/schemas/rag-ingestion.ts`.

---

### Requirement: Arsitektur Halaman

Halaman review SHALL mengikuti konvensi arsitektur frontend monorepo: `page.tsx` sebagai thin Suspense wrapper, `review-content.tsx` sebagai Client Component orchestrator, dan komponen private di `_components/`.

#### Scenario: page.tsx tidak punya logic

Diberikan `page.tsx` diinspeksi, maka MUST hanya berisi Suspense wrapper yang merender `ReviewContent` tanpa state, hooks, atau logic lain.

#### Scenario: API boundary tidak dilanggar

Diberikan `review-content.tsx` dan semua file di `_components/`, maka MUST NOT ada import `axios` langsung atau panggilan `fetch` ke API backend — semua request MUST melalui hooks di `use-rag-ingestion/`.

