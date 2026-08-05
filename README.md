# open-grounding

**Open Grounding** adalah platform RAG open-source yang menangani prompt dari MCP client — memutuskan apakah sebuah pertanyaan dijawab dari knowledge base (RAG grounded) atau langsung diteruskan ke LLM general.

Platform ini menerima dokumen, memrosesnya melalui pipeline ingestion (parse → chunk → embed → index), lalu menjawab pertanyaan dengan jawaban yang dikutip langsung dari dokumen — bukan dari halusinasi model.

---

## Cara Kerja

```
Prompt dari MCP client
        │
        ▼
  Query Router
  ┌─────────────────────────────┐
  │  RAG route?                 │
  │  → hybrid retrieval         │
  │  → reranking                │
  │  → confidence gate          │
  │  → grounded answer + citations │
  │                             │
  │  General route?             │
  │  → langsung ke LLM          │
  └─────────────────────────────┘
        │
        ▼
  Streaming answer ke client
```

Routing diputuskan oleh query analyzer berdasarkan intent, ketersediaan evidence, dan confidence threshold. Jika evidence tidak cukup, platform abstain — tidak mengarang jawaban.

---

## Stack

```
open-grounding/
├── apps/
│   ├── web/      → Next.js 16 App Router (Open Grounding Console)
│   ├── api/      → FastAPI (Clean Architecture, Python)
│   └── worker/   → BullMQ (ingestion pipeline background jobs)
└── packages/
    ├── schemas/  → Zod validation schemas (shared FE + Worker)
    ├── types/    → API response TypeScript types (shared FE)
    └── utils/    → Pure utility functions (shared FE + Worker)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 + Tailwind + Vitest |
| Backend API | FastAPI + SQLAlchemy async + Alembic + Pytest |
| Background worker | BullMQ + Redis |
| Vector store | Qdrant (hybrid dense + sparse) |
| Object store | MinIO (S3-compatible) |
| Metadata store | PostgreSQL |
| Cache & queue | Redis |
| Package manager | Bun |
| Task runner | Turbo |
| Lint/format | Biome |

---

## Arsitektur Singkat

### Offline knowledge plane (Ingestion)

```
Upload dokumen (PDF / Markdown / TXT)
  → Intake & validasi
  → Object store (file mentah + parser artefak)
  → BullMQ pipeline: Parse → Normalize → Chunk → Embed → Index
  → Qdrant (dense + sparse vectors + payload index)
  → PostgreSQL (manifest, lifecycle, version, trace)
```

Pipeline bersifat idempotent dan versioned. Setiap document version punya state machine:
`RECEIVED → STORED → QUEUED → PARSING → ... → READY` (atau `FAILED`).

### Online answer plane (Retrieval)

```
Query + knowledge base IDs
  → Auth + tenant + ACL filter
  → Standalone query + intent analysis
  → Route: RAG | General | Clarify | Abstain
  → Hybrid retrieval (dense + sparse + RRF)
  → Cross-encoder reranking
  → Confidence gate
  → Context builder + citation IDs
  → Grounded generation (streaming SSE)
  → Citation + groundedness validation
  → Streamed answer + citations + limitations
```

Jawaban hanya digenerate jika evidence cukup. Jika tidak, platform menjawab dengan `clarify` atau `abstain` — tidak mengarang.

---

## Open Grounding Console

Console web untuk operator:

| Route | Fungsi |
|---|---|
| `/login` | Login via NextAuth credentials |
| `/console` | Overview + quick-start guide |
| `/console/ingestion` | Upload dokumen + track status pipeline |
| `/console/retrieval` | Tanya jawab grounded + citations + feedback |
| `/console/settings` | Status platform + tenant info |

---

## Quick Start

Prerequisites:
- Bun `>= 1.3`
- Docker

```bash
bun install
bun run bootstrap
bun run dev
```

`bun run bootstrap` akan:
- Copy `.env.example` ke `.env` jika belum ada
- Start PostgreSQL, Redis, Qdrant, dan MinIO via Docker
- Tunggu sampai semua service ready
- Apply Alembic baseline migration
- Generate merged OpenAPI spec

Setelah bootstrap, init OpenSpec untuk planning layer:

```bash
bunx openspec init
```

---

## Endpoints

| Service | URL |
|---|---|
| Web (Console) | `http://localhost:3010` |
| Web login | `http://localhost:3010/login` |
| API root | `http://localhost:3011/` |
| API health | `http://localhost:3011/health` |
| OpenAPI spec | `docs/openapi.json` |

---

## Infrastruktur Docker

| Service | Port host | Fungsi |
|---|---|---|
| PostgreSQL | `5433` | Metadata, lifecycle, trace |
| Redis | `6380` | Queue (BullMQ) + cache |
| Qdrant | `6334` | Vector store (dense + sparse) |
| MinIO API | `9100` | Object store (file + artefak) |
| MinIO Console | `9101` | MinIO admin UI |

```bash
bun run stack:up       # start semua service
bun run stack:down     # stop semua service
bun run stack:logs     # lihat logs postgres + redis
bun run stack:reset    # stop + hapus semua volume (data hilang)
```

---

## Perintah Harian

```bash
bun run session:status     # cek status repo + MCP + task aktif
bun run db:upgrade         # apply migrasi Alembic terbaru
bun run openapi:generate   # regenerate docs/openapi.json
bun run lint               # Biome lint semua workspace
bun run typecheck          # TypeScript typecheck
bun run test               # semua test
bun run build              # build semua workspace
```

---

## Quality Checks

```bash
bun run check
```

Menjalankan: skill validation + network boundary check + lint + typecheck + test + smoke test + build.

---

## OpenAPI & Scalar

- Source of truth: FastAPI routers + Pydantic models
- Generated artifact: `docs/openapi.json`
- Scalar config: `apps/api/scalar.config.json`
- Generate: `bun run openapi:generate`

Jangan edit `docs/openapi.json` langsung — update FastAPI/Pydantic lalu regenerate.

---

## Vibe Coding Flow

Feature development menggunakan AI agents (Claude Code / Codex). Planning via [OpenSpec](https://github.com/Fission-AI/OpenSpec), implementation via **skills**.

### Start Session

Ketik **"Mulai"** atau **"Start"** di Claude Code / Codex. Agent akan:
1. Cek MCP status
2. Cek branch dan task aktif
3. Arahkan ke langkah berikutnya

### Phase 1 — Propose

```
/opsx:propose "nama fitur"

Output: openspec/changes/{slug}/
          proposal.md
          specs/
          design.md
          tasks.md
```

### Phase 2 — Implement

| Sub-phase | Skill | Target |
|---|---|---|
| FE Slicing | `web-slicing` | `apps/web/app/` |
| Backend + OpenAPI | `api-feature` + `docs-openapi` | `apps/api/app/` |
| FE ↔ API Integration | `web-api-integrated` | `packages/` + `apps/web/hooks/` |

### Phase 3 — Verify & Archive

```
/opsx:verify    → validasi implementasi
/opsx:archive   → archive specs
```

Skill registry lengkap ada di `.agents/AGENTS.md`.

---

## MCP Setup

Required MCP: `github`

Config dibaca dari `.mcp.json` di root repo (gitignored karena berisi token).

Jika baru clone:
1. Buat `.mcp.json` dengan GitHub token
2. Isi `.agents/settings.json` untuk `repo.owner` dan `repo.name`
3. Jalankan `bun run session:status`

---

## Delivery Phases

| Phase | Status | Cakupan |
|---|---|---|
| A — Platform foundation | ✅ Done | FastAPI + PostgreSQL + tenant schema |
| B — Reliable ingestion | ✅ Done | Upload PDF/MD/TXT → pipeline → Qdrant |
| C — Grounded query | ✅ Done | Auth filter + hybrid retrieval + streaming answer + citations |
| D — Production quality | 🔄 In progress | Evaluation, observability, connectors, tool gateway |
| E — Advanced retrieval | ⏳ Planned | Graph retrieval, ColBERT, multimodal |

---

## Contributing

1. Fork atau buat branch baru dari `main`
2. `bun install && bun run bootstrap`
3. Pastikan `bun run check` pass
4. Jika menyentuh `.agents/skills/`, jalankan `bun run skills:sync && bun run skills:validate`
5. Buka pull request

---

## License

[MIT](./LICENSE)
