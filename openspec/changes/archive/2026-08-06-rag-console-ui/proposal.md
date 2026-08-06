## Why

The RAG platform backend is operational (auth, ingestion, grounded query with SSE streaming,
traces, feedback, readiness) but it has no user-facing surface. Operators and users currently
have no way to upload documents, watch ingestion progress through the worker pipeline, ask
grounded questions, inspect citations, or review platform health and configuration without
calling raw HTTP endpoints. A simple, clean, and elegant console is needed so the platform can
be driven end-to-end from a browser: login, ingest documents until the worker finishes
processing them, retrieve grounded answers, and view setup/config — all behind the existing
NextAuth BFF proxy.

## What Changes

- Introduce an authenticated **console app shell** in `apps/web` that reuses the existing
  NextAuth credentials login (`/login`) and renders a clean, responsive sidebar/topbar layout
  for all post-login routes. Add route guards so every console route requires an active session
  and redirects to login when the session expires.
- Add an **ingestion workbench** UI that drives the existing `/rag/ingestion/*` endpoints:
  create intake, upload to the presigned target, complete intake, and poll ingestion status to
  show the worker pipeline stages (parse → embed → index) through to a terminal state. List
  document versions tenant-scoped, soft-delete, and surface quality outcome.
- Add a **retrieval conversation** UI against `/rag/query`: compose a question with a knowledge
  base selector, stream SSE answer events in order (route, retrieval summary, deltas,
  citations, limitations, completion), render citations with snippet and locator, continue
  conversations, and submit answer feedback.
- Add a **settings console** UI against `/ready`, `/health`, `/auth/tenant/context`, and the
  knowledge-catalog surface: show dependency readiness without secrets, server-derived tenant
  context as read-only, knowledge bases, and model/index profile metadata without credentials.
- Extend shared `packages/schemas` with RAG Zod schemas (intake, complete, query, feedback,
  status) and `packages/types` with RAG response types so the frontend validates and types every
  RAG contract shared with the backend.
- Wire `apps/web/constants/api-routers.ts` and `query-keys.ts` with the RAG routers/keys and add
  the matching React Query hooks + services under the established `web-api-integrated` pattern.

## Capabilities

### New Capabilities

- `rag-console-app-shell`: Authenticated post-login shell — layout, sidebar/topbar navigation,
  session-enforced route guards, session-expiry handling, clean/elegant design system, and BFF
  proxy usage with no client-side secrets.
- `rag-ingestion-workbench-ui`: Document intake workbench — presigned upload flow, document
  version list, ingestion status surfacing worker pipeline stages to completion, retry/delete,
  and quality outcome display.
- `rag-retrieval-conversation-ui`: Retrieval chat — query composer with knowledge-base
  selector, ordered SSE streaming answers, citation rendering with locator, conversation
  continuity, and answer feedback.
- `rag-settings-console-ui`: Settings & config — readiness/health dashboard, server-derived
  tenant context viewer, knowledge-base management, and non-secret model/index profile visibility.

### Modified Capabilities

None. This change adds frontend UI capabilities that consume the existing backend specs
(`rag-source-intake-and-versioning`, `rag-ingestion-operations`, `rag-grounded-answer-generation`,
`rag-infrastructure-runtime`, `rag-provider-ports`, `tenant-context-and-isolation`). It does not
change any spec-level backend behavior.

## Impact

- **Frontend (`apps/web`)**: new app routes (`/console/*`), layout, navigation, ingestion,
  retrieval, and settings pages; new hooks, services, constants, and types under the existing
  folder contracts; reuse of the existing component library and BFF proxy.
- **Shared packages**: `packages/schemas` gains RAG Zod schemas; `packages/types` gains RAG
  response types. No backend package changes.
- **Backend (`apps/api`)**: no code or contract changes. The UI only consumes existing
  endpoints through the proxy.
- **Worker (`apps/worker`)**: no change required; the UI surfaces the status the API already
  reports. Worker queue registration remains a separate backend concern.
- **Dependencies**: no new runtime dependencies expected beyond the existing Next.js, React
  Query, Tailwind, and component library stack.