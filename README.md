# open-grounding

**Open Grounding** is an open-source RAG platform — a standalone backend that ingests documents, indexes them as vectors, and answers questions with responses grounded in and cited from those documents, not from model hallucination.

It is designed to be called by any external client or business orchestrator via REST API or MCP, making it suitable as the knowledge and retrieval layer for conversational agents, order flows, support bots, and similar applications.

---

## How It Works

A query goes through two stages before an answer is returned: **decomposition + routing**, then **grounding**.

### Stage 1 — Decomposition & Routing (async)

When a query arrives, the platform first analyzes intent and decomposes it into one or more sub-tasks. Each sub-task is routed independently and executed as an async job:

```
External client (REST API or MCP)
        │
        ▼
  POST /rag/query  →  job enqueued (returns jobId immediately)
        │
        ▼
  ┌─────────────────────────────────────────────┐
  │  Query Analysis & Decomposition             │
  │  → standalone query rewrite                 │
  │  → intent analysis                          │
  │  → decompose into sub-tasks (if needed)     │
  └──────────────────┬──────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    RAG task    General task  Tool task
    → hybrid    → pass to     → MCP tool
      retrieval   LLM           execution
    → reranking
    → confidence
      gate
```

Each sub-task type:

| Route | When | What happens |
|---|---|---|
| `RAG` | Query answerable from knowledge base | Hybrid retrieval → rerank → confidence gate → grounded generation |
| `General` | No relevant KB evidence | Passed directly to LLM without retrieval |
| `Tool` | Registered MCP tool matches intent | MCP tool executed, result injected into context |
| `Abstain` | Insufficient evidence + low confidence | Platform declines to answer — never fabricates |

### Stage 2 — Grounding & Answer Assembly

After all sub-tasks complete, results are merged into a single grounded response:

```
  Sub-task results (RAG chunks + tool output + general LLM)
        │
        ▼
  Context builder + citation IDs
        │
        ▼
  Grounded generation (LLM with evidence-only prompt)
        │
        ▼
  Answer + citations + limitations  →  client (polled via GET /rag/query/{jobId})
```

The client polls `GET /rag/query/{jobId}` for the result, or receives it via webhook if configured. Answers only reference cited evidence — if evidence is insufficient, the platform responds with `abstain` rather than fabricating.

---

## How It Works (summary diagram)

```
Client
  │
  ├── POST /rag/query ─────────────────────────────┐
  │         returns: { jobId }                      │
  │                                                 ▼
  │                                    Decompose → route tasks async
  │                                    ┌──────────────────────────┐
  │                                    │  RAG   General   Tool    │
  │                                    └──────────┬───────────────┘
  │                                               ▼
  │                                    Ground + assemble answer
  │
  └── GET /rag/query/{jobId} ◄── poll for result
            returns: { answer, citations, limitations }
```

---

## Stack

```
open-grounding/
├── apps/
│   ├── web/      → Next.js 16 App Router (Open Grounding Console)
│   └── api/      → FastAPI (Clean Architecture, Python)
│                   └── app/workers/  → BullMQ Python workers (ingestion + query)
└── packages/
    ├── schemas/  → Zod validation schemas (shared FE)
    ├── types/    → API response TypeScript types (shared FE)
    └── utils/    → Pure utility functions (shared FE)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 + Tailwind + Vitest |
| Backend API | FastAPI + SQLAlchemy async + Alembic + Pytest |
| Background workers | BullMQ + Redis (Python, co-located in `apps/api`) |
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
  → Object store (raw file)
  → BullMQ pipeline: Parse → [Human Review gate] → Chunk → Embed → Index
  → Qdrant (dense + sparse vectors + payload index)
  → PostgreSQL (manifest, lifecycle, version, trace)
```

The pipeline is versioned and has a human review gate. Each document version has a state machine:
`RECEIVED → STORED → QUEUED → PARSING → NEEDS_REVIEW → CHUNKING → EMBEDDING → INDEXING → READY`

When human review is enabled on a knowledge base, the pipeline halts at `NEEDS_REVIEW` and waits for operator approval before indexing continues.

### Online answer plane (Retrieval)

```
POST /rag/query  →  job enqueued  →  returns jobId
  │
  ▼
Query Analysis & Decomposition
  → standalone query rewrite
  → intent analysis
  → decompose into sub-tasks (RAG / General / Tool / Abstain)
  │
  ├── RAG task    → hybrid retrieval (dense + sparse + RRF)
  │                → cross-encoder reranking
  │                → confidence gate
  │                → grounded generation
  │
  ├── General task → LLM direct (no retrieval)
  │
  └── Tool task   → MCP tool execution
  │
  ▼
Ground + assemble: context builder + citation IDs + grounded LLM call
  │
  ▼
GET /rag/query/{jobId}  →  answer + citations + limitations
```

Answers are only generated when evidence is sufficient. Otherwise the platform responds with `abstain` — never fabricates.

---

## Open Grounding Console

Web console for operators at `http://localhost:3010`:

| Route | Function |
|---|---|
| `/login` | Login via NextAuth credentials |
| `/console` | Overview dashboard |
| `/console/knowledge-bases` | Create and manage knowledge bases |
| `/console/knowledge-bases/[id]/ingestion` | Configure ingestion settings and human review |
| `/console/document` | Document list + pipeline status tracking |
| `/console/document/review/[versionId]` | Human review — approve or reject parsed content |
| `/console/query` | Grounded Q&A + citations + feedback |
| `/console/memory` | Conversation memory management |
| `/console/settings` | Providers, models, index profiles, MCP servers, confidence |

---

## Quick Start

Prerequisites:
- Bun `>= 1.3`
- Docker
- Python `>= 3.11` with `uv`

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

## Integrating with an External Orchestrator

Open Grounding is designed to be called by an external business orchestrator — a Node.js service, a LangGraph agent, an n8n workflow, or any HTTP client.

The orchestrator is responsible for domain-specific logic (order state, required field collection, business rules). Open Grounding handles:

- Decomposing and routing queries to RAG, General LLM, or MCP tools
- Executing tasks asynchronously and grounding the final answer against cited evidence
- Maintaining conversation history per `conversation_id`

**Typical integration flow:**

```
Business Orchestrator (Node.js / Python / etc.)
  │
  ├── Manage session state (Redis or DB)
  ├── Inject context via system prompt per request
  │
  ├── POST /rag/query
  │       {
  │         "message": "user message",
  │         "knowledge_base_ids": ["kb-id"],
  │         "conversation_id": "session-123"
  │       }
  │       ← { jobId: "job-xyz" }
  │
  ├── poll GET /rag/query/job-xyz
  │       until status === "completed"
  │
  └── receive { answer, citations, limitations }
        → grounded answer, never fabricated
```

The `conversation_id` is shared between the orchestrator and the platform, so conversation history accumulates naturally across turns. Alternatively, configure a `webhook_url` in the request body to receive the result via HTTP POST when the job completes — no polling needed.

---

## Vibe Coding Flow

Feature development uses AI agents (Claude / Codex). Planning is handled by [OpenSpec](https://github.com/Fission-AI/OpenSpec), implementation is guided by **skills**.

### Start a Session

Type **"Start"** or **"Mulai"** in Claude / Codex. The agent will:
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
| C — Grounded query | ✅ Done | Auth filter + hybrid retrieval + answer + citations |
| D — Production quality | 🔄 In progress | Evaluation, observability, human review, tool gateway |
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
