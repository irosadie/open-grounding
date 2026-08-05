# open-grounding

**Open Grounding** is an open-source RAG platform that handles prompts from MCP clients — deciding whether a question should be answered from a knowledge base (RAG grounded) or passed directly to a general LLM.

The platform ingests documents through a versioned pipeline (parse → chunk → embed → index), then answers questions with responses grounded in and cited from those documents — not from model hallucination.

---

## How It Works

```
Prompt from MCP client
        │
        ▼
  Query Router
  ┌─────────────────────────────────┐
  │  RAG route?                     │
  │  → hybrid retrieval             │
  │  → reranking                    │
  │  → confidence gate              │
  │  → grounded answer + citations  │
  │                                 │
  │  General route?                 │
  │  → pass directly to LLM         │
  └─────────────────────────────────┘
        │
        ▼
  Streaming answer to client
```

Routing is decided by a query analyzer based on intent, evidence availability, and confidence threshold. If evidence is insufficient, the platform abstains — it does not fabricate answers.

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

## Architecture Overview

### Offline knowledge plane (Ingestion)

```
Upload document (PDF / Markdown / TXT)
  → Intake & validation
  → Object store (raw file + parser artifacts)
  → BullMQ pipeline: Parse → Normalize → Chunk → Embed → Index
  → Qdrant (dense + sparse vectors + payload index)
  → PostgreSQL (manifest, lifecycle, version, trace)
```

The pipeline is idempotent and versioned. Each document version has a state machine:
`RECEIVED → STORED → QUEUED → PARSING → ... → READY` (or `FAILED`).

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

Answers are only generated when evidence is sufficient. Otherwise the platform responds with `clarify` or `abstain` — never fabricates.

---

## Open Grounding Console

Web console for operators:

| Route | Function |
|---|---|
| `/login` | Login via NextAuth credentials |
| `/console` | Overview + quick-start guide |
| `/console/ingestion` | Upload documents + track pipeline status |
| `/console/retrieval` | Grounded Q&A + citations + feedback |
| `/console/settings` | Platform health + tenant info |

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

`bun run bootstrap` will:
- Copy `.env.example` to `.env` if it does not exist
- Start PostgreSQL, Redis, Qdrant, and MinIO via Docker
- Wait for all services to be ready
- Apply the Alembic baseline migration
- Generate the merged OpenAPI spec

After bootstrapping, initialize OpenSpec for the planning layer:

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

## Docker Infrastructure

| Service | Host port | Purpose |
|---|---|---|
| PostgreSQL | `5433` | Metadata, lifecycle, trace |
| Redis | `6380` | Queue (BullMQ) + cache |
| Qdrant | `6334` | Vector store (dense + sparse) |
| MinIO API | `9100` | Object store (files + artifacts) |
| MinIO Console | `9101` | MinIO admin UI |

```bash
bun run stack:up       # start all services
bun run stack:down     # stop all services
bun run stack:logs     # tail postgres + redis logs
bun run stack:reset    # stop + remove all volumes (data loss)
```

---

## Daily Commands

```bash
bun run session:status     # check repo status, MCP, and active tasks
bun run db:upgrade         # apply latest Alembic migrations
bun run openapi:generate   # regenerate docs/openapi.json
bun run lint               # Biome lint across all workspaces
bun run typecheck          # TypeScript typecheck
bun run test               # run all tests
bun run build              # build all workspaces
```

---

## Quality Checks

```bash
bun run check
```

Runs: skill validation + network boundary check + lint + typecheck + test + smoke test + build.

---

## OpenAPI & Scalar

- Source of truth: FastAPI routers + Pydantic models
- Generated artifact: `docs/openapi.json`
- Scalar config: `apps/api/scalar.config.json`
- Generate: `bun run openapi:generate`

Do not edit `docs/openapi.json` directly — update FastAPI/Pydantic models and regenerate.

---

## Vibe Coding Flow

Feature development uses AI agents (Claude Code / Codex). Planning is handled by [OpenSpec](https://github.com/Fission-AI/OpenSpec), implementation is guided by **skills**.

### Start a Session

Type **"Start"** or **"Mulai"** in Claude Code / Codex. The agent will:
1. Check MCP status
2. Check active branch and in-progress tasks
3. Direct you to the next step

### Phase 1 — Propose

```
/opsx:propose "feature name"

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
/opsx:verify    → validate implementation against specs
/opsx:archive   → archive the completed change
```

Full skill registry is in `.agents/AGENTS.md`.

---

## MCP Setup

Required MCP: `github`

Config is read from `.mcp.json` at the repo root (gitignored — contains real tokens).

If you just cloned:
1. Create `.mcp.json` with your GitHub token
2. Fill in `.agents/settings.json` for `repo.owner` and `repo.name`
3. Run `bun run session:status`

---

## Delivery Phases

| Phase | Status | Scope |
|---|---|---|
| A — Platform foundation | ✅ Done | FastAPI + PostgreSQL + tenant schema |
| B — Reliable ingestion | ✅ Done | Upload PDF/MD/TXT → pipeline → Qdrant |
| C — Grounded query | ✅ Done | Auth filter + hybrid retrieval + streaming answer + citations |
| D — Production quality | 🔄 In progress | Evaluation, observability, connectors, tool gateway |
| E — Advanced retrieval | ⏳ Planned | Graph retrieval, ColBERT, multimodal |

---

## Contributing

1. Fork or create a branch from `main`
2. `bun install && bun run bootstrap`
3. Make your changes
4. Ensure `bun run check` passes
5. If touching `.agents/skills/`, run `bun run skills:sync && bun run skills:validate`
6. Open a pull request

---

## License

[MIT](./LICENSE)
