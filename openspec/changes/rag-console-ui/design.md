## Context

The RAG platform backend is live in `apps/api`: NextAuth-compatible auth, presigned object-store
intake with worker-enqueued ingestion, grounded query with SSE streaming, traces, feedback,
and a readiness diagnostic covering PostgreSQL, Redis, Qdrant, object storage, tenant, and
index profiles. The web app (`apps/web`, Next.js App Router) already ships a NextAuth
credentials login, a BFF proxy at `/api/proxy/[...path]` that injects and refreshes the access
token, React Query, Tailwind, a broad component library, and shared `packages/schemas` +
`packages/types` (currently auth-only). The worker (`apps/worker`) is a BullMQ scaffold; the
API enqueues ingestion jobs and exposes status, so the UI can surface pipeline progress without
depending on worker internals.

There is currently no post-login UI: the homepage is a starter placeholder. The user needs a
simple, clean, elegant console covering login → ingestion (worker to completion) → retrieval →
setup/config.

## Goals / Non-Goals

**Goals:**

- Ship one cohesive console UI with four work areas (shell, ingestion, retrieval, settings)
  behind the existing NextAuth login and BFF proxy.
- Drive every action through the existing backend endpoints via the proxy; never call the API
  directly from the browser and never hold backend secrets client-side.
- Surface the ingestion worker pipeline stages through to a terminal state using the status
  endpoint, without coupling the UI to worker internals.
- Render streaming grounded answers in order with citations, evidence level, limitations, and
  feedback, matching the SSE contract the backend already emits.
- Keep the UI accessible, responsive, and consistent with the existing design system and Biome
  rules.

**Non-Goals:**

- Modify any backend API contract, schema, migration, or endpoint. The UI only consumes.
- Implement worker queue registration or ingestion processing logic; that stays in
  `apps/worker` / `apps/api`.
- Add new auth providers or SSO. The existing credentials login is reused as-is.
- Build admin-only trace inspection UI beyond what the trace/feedback endpoints expose.
- Introduce a new styling system or component library; reuse the existing one.

## Decisions

### Reuse the existing NextAuth credentials login; do not rebuild auth

The login page, NextAuth options, proxy token refresh, and route guard primitives already
exist. Rebuilding auth risks regressions and adds no value. The console shell starts after
`/login` redirects to the console root and reuses the same session/JWT/refresh flow.

### Single console root under `/console/*` with a shared layout

All post-login routes live under an App Router segment group `/console/*` with one shared
`layout.tsx` rendering the sidebar, topbar, session-aware guards, and the React Query scope.
This keeps the shell, navigation, and guards in one place and leaves `/` and `/login`
unchanged. The existing `proxy.ts` matcher is extended to protect `/console/*`.

### Every backend call goes through the BFF proxy; shared schemas validate client-side

The proxy already injects the access token, refreshes near expiry, and retries on 401. New
hooks call `/api/proxy/rag/...` only. Zod schemas in `packages/schemas` (intake, complete,
query, feedback, status) and response types in `packages/types` mirror the backend Pydantic
models so the frontend validates before sending and types every response, matching the
established `web-api-integrated` pattern.

### Ingestion status is polled; the UI never depends on worker internals

The status endpoint reports lifecycle state, current stage, attempts, and quality. The UI
polls it at a bounded interval while a version is non-terminal and renders a stepper
(parse → embed → index → ready/failed) driven by the reported stage — not by worker queue
internals. This keeps the UI correct even if the worker implementation changes.

### Retrieval renders SSE events strictly in the emitted order

The backend emits `response.started`, `response.route`, `response.retrieval_summary`,
`response.delta`, `response.citations`, `response.completed` (and `response.failed`). The UI
consumes the stream via the proxy with `text/event-stream`, appends deltas in order, and only
renders citations/limitations after the completion event. Non-streaming fallback uses the
single JSON response. This matches the SSE contract exactly.

### Settings is read-only by default; writes only where the backend supports them

The backend exposes readiness, tenant context, and (via the catalog) knowledge bases and
profile metadata, but most are read surfaces. The settings console renders these read-only to
avoid implying writes the backend does not support, and never displays provider secrets
(consistent with `rag-provider-ports`).

## Risks / Trade-offs

- [SSE through a Next.js BFF proxy may buffer or break streaming] → Use a pass-through proxy
  response with `text/event-stream` and disable buffering; verify in a smoke test. Provide a
  non-streaming fallback when the proxy cannot stream.
- [Polling ingestion status can be noisy] → Poll only while a version is non-terminal, use a
  bounded interval with backoff, and stop on terminal state or unmount.
- [Shared schema drift from backend Pydantic models] → Keep schemas co-located and reviewed
  against `apps/api/app/interfaces/http/schemas.py`; treat the backend models as the source of
  truth.
- [Settings implying writes that don't exist] → Render config as read-only unless a backend
  write endpoint exists; label clearly.
- [Session expiry mid-task] → The proxy already refreshes; on terminal 401, redirect to
  `/login` with a callback URL and surface a toast.

## Migration Plan

1. Add shared RAG schemas and types (no UI impact).
2. Ship the app shell + route guard first (login already works; users land in an empty console).
3. Ship ingestion workbench (upload + status polling).
4. Ship retrieval conversation (streaming + citations + feedback).
5. Ship settings console (readiness + tenant + KB + profiles).
6. Extend `proxy.ts` protection to `/console/*`; verify token refresh and 401 redirect.
No backend migration is required; rollback is deleting the new `apps/web` routes and packages
exports (backend remains unchanged).

## Open Questions

- Should the console root be `/console` (segment group) or replace `/` as the post-login home?
  Leaning `/console/*` to keep the starter homepage intact.
- Does the proxy need an explicit streaming path allow-list, or is `text/event-stream` enough
  to avoid buffering in the Node runtime?
- Is a knowledge-base create/write endpoint in scope for this change, or is listing read-only
  for now (backend may not expose KB writes yet)?