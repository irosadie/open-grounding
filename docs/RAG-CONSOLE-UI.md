# RAG Console UI

A simple, clean, and elegant console for the RAG platform: login, document ingestion
through the worker pipeline, grounded retrieval with streaming and citations, and
settings/config.

## Console Routes

All post-login routes live under `/console/*` and require an authenticated NextAuth
session. The middleware (`apps/web/middleware.ts`, sourced from `apps/web/proxy.ts`)
redirects unauthenticated users to `/login` with a `callbackUrl`, and redirects
authenticated users on `/login` to `/console`.

| Route | Work area | Description |
| --- | --- | --- |
| `/login` | Auth | Existing NextAuth credentials login (reused). |
| `/console` | Overview | Platform summary and links to all work areas. |
| `/console/ingestion` | Ingestion | Upload documents and track the worker pipeline to completion. |
| `/console/retrieval` | Retrieval | Ask grounded questions with streaming answers, citations, and feedback. |
| `/console/settings` | Settings | Readiness dashboard, tenant context, and read-only config. |

## Architecture

- **BFF proxy**: every backend call goes through `/api/proxy/[...path]`, which injects
  the access token from the NextAuth JWT cookie and refreshes near expiry. UI components
  never call the API directly.
- **Streaming BFF**: SSE responses go through `/api/stream/[...path]`, a dedicated route
  that passes `text/event-stream` through without buffering and falls back to a normal
  response for non-streaming content.
- **Shared contracts**: Zod schemas live in `packages/schemas` (`rag-ingestion.ts`,
  `rag-query.ts`); response types live in `packages/types` (`rag-ingestion-response.ts`,
  `rag-query-response.ts`, `rag-system-response.ts`). They mirror the backend Pydantic
  models in `apps/api/app/interfaces/http/schemas.py`.
- **Hooks**: transaction hooks in `apps/web/hooks/transactions/` follow the
  `web-api-integrated` pattern (one folder per domain, axios via the service layer).

## Ingestion Flow

1. Select a knowledge base id and a supported file (PDF, Markdown, or plain text).
2. The UI creates an intake (`POST /rag/ingestion/intake`), computes a SHA-256 checksum,
   and completes intake (`POST /rag/ingestion/complete`).
3. The UI polls ingestion status (`GET /rag/ingestion/status/{document_version_id}`) at a
   bounded interval and renders a pipeline stepper (Upload → Parse → Embed → Index → Ready)
   driven by the reported lifecycle state. Polling stops on a terminal state (Ready/Failed).
4. Soft-delete is available on terminal versions (`DELETE /rag/ingestion/{document_version_id}`)
   after explicit confirmation.

## Retrieval Flow

- Compose a question with one or more knowledge base ids and submit.
- The UI streams SSE events in emitted order: `started`, `route`, `retrieval_summary`,
  `delta`, `citations`, `completed` (or `failed`). Answer deltas appear progressively;
  citations and limitations render after the completion event.
- `clarify` and `abstain` routes and low/none evidence levels are surfaced distinctly
  from a grounded answer.
- After completion, you can submit 1-5 rating and optional comment feedback against the
  retained trace (`POST /rag/query/traces/{trace_id}/feedback`).

## Settings

- **Readiness**: dependency health (PostgreSQL, Redis, Qdrant, object storage, tenant,
  index profile) from `/ready`, with no secrets.
- **Tenant context**: server-derived tenant, membership, and user identity from
  `/auth/tenant/context`, shown read-only.
- **Knowledge bases & profiles**: read-only until catalog write endpoints are available.

## Run Locally

```bash
# from repo root
bun run --filter @vibecoding-starter/web dev    # web on :3000
bun run --filter @vibecoding-starter/api dev    # api on :3001 (FastAPI)
```

The web app proxies backend calls to the API using `API_URL` (see
`apps/web/configs/auth-server.ts`). Log in with valid credentials and you will land on
`/console`.

## Quality Gates

- `bun run --filter @vibecoding-starter/web lint` — Biome (no `any`, no `console.*`,
  `const`, double quotes, no semicolons).
- `bun run --filter @vibecoding-starter/web typecheck` — `next typegen && tsc --noEmit`.
- `bun run --filter @vibecoding-starter/web test` — vitest smoke + unit tests.
- `openspec validate rag-console-ui` — OpenSpec change validation.
