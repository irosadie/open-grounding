## Why

Nama `vibecoding-starter` adalah nama template generik yang tidak mencerminkan identitas produk. Nama UI `RAG Console` / `RAG Platform` juga terlalu teknis dan tidak memiliki brand yang kuat. Rebrand ke `open-grounding` memberikan identitas yang jelas, mudah diingat, dan mencerminkan fungsi utama platform: grounded retrieval dari dokumen.

## What Changes

- **Package names**: `@vibecoding-starter/schemas`, `@vibecoding-starter/types`, `@vibecoding-starter/utils` → `@open-grounding/schemas`, `@open-grounding/types`, `@open-grounding/utils`
- **Repo/project name**: `vibecoding-starter` → `open-grounding` (di `package.json` root, turbo filter, container names, DB names, dll)
- **UI brand**: `RAG Console` → `Open Grounding Console` (topbar, page title, metadata)
- **UI brand**: `RAG Platform` → `Open Grounding Platform` (docs, settings page)
- **Docker container names**: `vibecoding-starter-*` → `open-grounding-*`
- **Database name**: `open_grounding` → `open_grounding`
- **Python venv prompt**: `open-grounding-api` → `open-grounding-api`
- **API app name**: `open-grounding-api` → `open-grounding-api`
- **Docs & README**: semua referensi nama brand diupdate

## Capabilities

### New Capabilities
_(tidak ada kapabilitas baru — ini perubahan non-fungsional)_

### Modified Capabilities
_(tidak ada perubahan requirement — hanya rename brand/identifier)_

## Impact

- `package.json` (root, apps/web, apps/api, apps/worker, packages/*)
- `tsconfig*.json` di semua workspace yang punya path alias `@vibecoding-starter/*`
- `apps/web/` — semua import `@vibecoding-starter/*`, UI strings, metadata
- `apps/api/` — app name di system route, pyproject.toml jika ada
- `apps/worker/` — package name
- `docker-compose.yml` — container names, DB name
- `apps/api/.env` + `.env.example` — DATABASE_URL
- `apps/web/.env.example`
- `apps/worker/.env.example`
- `docs/` — semua referensi nama brand
- `README.md`
- `.agents/` — settings.json, guides, examples yang referensi package name
- `bun.lock` — perlu di-regenerate setelah rename packages
