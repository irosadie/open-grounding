## Context

Repo saat ini menggunakan nama `vibecoding-starter` sebagai identitas di seluruh monorepo (package names, container names, DB name, UI strings). Nama ini adalah sisa dari template awal dan tidak mencerminkan produk yang dibangun. Rebrand ini bersifat non-fungsional — tidak ada perubahan behavior, API contract, atau data model.

Dua lapisan yang diubah:
1. **Identifier teknis** — package names (`@vibecoding-starter/*`), project name di `package.json`, container names, DB name
2. **UI strings** — label yang muncul di browser: topbar, page title, `<title>` metadata, docs

## Goals / Non-Goals

**Goals:**
- Ganti semua `vibecoding-starter` → `open-grounding` di file konfigurasi, package.json, tsconfig path alias, docker-compose, .env, dan docs
- Ganti UI strings `RAG Console` / `RAG Platform` → `Open Grounding Console` / `Open Grounding Platform`
- Regenerate `bun.lock` setelah rename packages
- Pastikan semua import `@vibecoding-starter/*` di source files diganti ke `@open-grounding/*`

**Non-Goals:**
- Tidak mengubah nama folder/direktori (apps/web, apps/api, dll tetap sama)
- Tidak mengubah slug OpenSpec changes yang sudah ada
- Tidak mengubah git remote atau GitHub repo name (user melakukan sendiri jika perlu)
- Tidak mengubah nama branch aktif

## Decisions

### 1. Ganti package name sekaligus, bukan bertahap
Karena semua package (`schemas`, `types`, `utils`) diimport bersama, rename bertahap akan menyebabkan import mismatch sementara. Lebih aman rename semua sekaligus lalu regenerate lockfile sekali.

### 2. DB name: `open_grounding` → `open_grounding`
Hanya di konfigurasi (`.env`, `docker-compose.yml`). Container sudah menggunakan named volume — data tidak hilang selama volume tidak dihapus. Jika container sudah berjalan, perlu `docker-compose down && docker-compose up -d` agar nama DB baru berlaku (atau rename DB manual di psql).

### 3. UI string: tetap deskriptif
`RAG Console` → `Open Grounding Console` (bukan hanya `Open Grounding`) agar konteks "console" tetap jelas di topbar dan tab browser.

### 4. `.agents/` examples dan guides: ganti hanya yang merupakan import path aktif
File di `.agents/examples/` dan `.agents/guides/` adalah referensi kode untuk agent — import `@vibecoding-starter/*` di sana juga harus diganti agar tidak menyebabkan agent menghasilkan kode dengan import lama.

## Risks / Trade-offs

- **bun.lock conflict** → setelah rename package.json, jalankan `bun install` untuk regenerate lockfile. Jangan commit lockfile lama.
- **DB sudah ada data** → rename DB hanya di config, bukan di data volume. Jika DB sudah dibuat dengan nama lama, perlu rename manual: `ALTER DATABASE open_grounding RENAME TO open_grounding;`
- **IDE cache** → setelah rename tsconfig path alias, restart TypeScript server di IDE agar path resolution tidak cache alias lama.
- **`.vscode/PythonImportHelper-v2-Completion.json`** → file ini auto-generated oleh VS Code extension, tidak perlu diubah manual.

## Migration Plan

1. Rename semua `package.json` (root + apps/* + packages/*)
2. Rename tsconfig path aliases di semua `tsconfig.json`
3. Rename semua import `@vibecoding-starter/*` di source files
4. Update `docker-compose.yml` — container names + DB name
5. Update `.env` + `.env.example` files — DATABASE_URL
6. Update UI strings di `apps/web/`
7. Update `apps/api/` — app name di system route response
8. Update docs + README
9. Update `.agents/` — settings.json + examples + guides
10. Jalankan `bun install` untuk regenerate lockfile
11. Jalankan `bun run typecheck` + `bun run lint` untuk verifikasi

Rollback: semua perubahan adalah string replacement — revert via git jika ada masalah.

## Open Questions

- Apakah nama DB di container yang sudah berjalan perlu direname manual, atau cukup fresh start? → **Asumsi: fresh start (dev environment), tidak ada data produksi.**
