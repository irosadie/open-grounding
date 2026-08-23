## 1. Shared RAG contracts (schemas, types, constants)

- [x] 1.1 Add Zod schemas to `packages/schemas` for create-intake, complete-intake,
  ingestion-status, rag-query, and answer-feedback, mirroring
  `apps/api/app/interfaces/http/schemas.py`.
- [x] 1.2 Add RAG response types to `packages/types` (intake response, ingestion status, query
  response, citation, SSE event payloads, readiness report, tenant context).
- [x] 1.3 Extend `apps/web/constants/api-routers.ts` with `rag` routers (ingestion intake,
  complete, status, delete, query, traces, feedback) and `system` routers (health, ready,
  tenant context).
- [x] 1.4 Extend `apps/web/constants/query-keys.ts` with matching RAG and system query keys.
- [x] 1.5 Export new schemas/types from package barrels and run `bun run typecheck` for
  `packages/*` and `apps/web`.

## 2. Console app shell and route guards

- [x] 2.1 Create the `/console/*` App Router segment group with a shared `layout.tsx`
  rendering the sidebar, topbar, session-aware guard, and React Query scope.
- [x] 2.2 Extend `apps/web/proxy.ts` to protect `/console/*` (redirect to `/login` with
  `callbackUrl` when unauthenticated; redirect `/login` to console when authenticated).
- [x] 2.3 Implement the session-expiry handler: on terminal proxy 401, redirect to `/login`
  with a callback URL and surface a non-blocking session-expired toast.
- [x] 2.4 Build the navigation with active-route highlighting and keyboard-operable, visible
  focus indicators using the existing component library.
- [x] 2.5 Add an overview/console root page and verify the shell renders after login.

## 3. Ingestion workbench UI

- [x] 3.1 Add a `use-ingestion-intake` hook + service calling `/api/proxy/rag/ingestion/intake`
  with client-side file type/size validation (PDF, Markdown, plain text).
- [x] 3.2 Add a `use-ingestion-complete` hook + service calling
  `/api/proxy/rag/ingestion/complete` with the content checksum after presigned upload.
- [x] 3.3 Add a `use-ingestion-status` polling hook calling
  `/api/proxy/rag/ingestion/status/{document_version_id}` with a bounded interval and backoff,
  stopping on terminal state or unmount.
- [x] 3.4 Build the pipeline stepper (parse → embed → index → ready/failed) driven by the
  reported stage, attempts, and quality outcome.
- [x] 3.5 Add the document version list (tenant-scoped, paginated/virtualized) with lifecycle
  state and current stage per row.
- [x] 3.6 Add soft-delete with explicit confirmation calling
  `DELETE /api/proxy/rag/ingestion/{document_version_id}` and reflecting the scheduled state.
- [x] 3.7 Wire the upload UI (file picker/dropzone using the existing file component) to the
  intake → upload → complete flow.

## 4. Retrieval conversation UI

- [x] 4.1 Add a `use-rag-query` hook for the non-streaming JSON path via
  `/api/proxy/rag/query` with knowledge-base selector and message validation.
- [x] 4.2 Add a streaming consumer for `/api/proxy/rag/query` with `stream=true` parsing
  `text/event-stream` events in emitted order (started, route, retrieval_summary, delta,
  citations, completed, failed).
- [x] 4.3 Build the conversation view that appends deltas progressively and renders citations,
  evidence level, and limitations only after the completion event.
- [x] 4.4 Render citations with title, snippet, and locator, linking to the source in the
  ingestion workbench when authorized; never show raw vectors or hidden prompts.
- [x] 4.5 Surface `clarify` and `abstain` routes and low/none evidence levels distinctly from a
  grounded answer, displaying stated limitations.
- [x] 4.6 Add answer feedback (1-5 rating + bounded comment) via
  `/api/proxy/rag/query/traces/{trace_id}/feedback`, disabling when the trace is unavailable.

## 5. Settings console UI

- [x] 5.1 Add a `use-readiness` hook calling `/api/proxy/ready` and render the dependency
  health dashboard (PostgreSQL, Redis, Qdrant, object storage, tenant, index profile) without
  secrets.
- [x] 5.2 Add a `use-tenant-context` hook calling `/api/proxy/auth/tenant/context` and render
  tenant/membership/user as read-only.
- [x] 5.3 Add a knowledge-base list panel scoped to the tenant using the catalog surface.
- [x] 5.4 Add read-only model/index profile metadata panels (provider references, dimensions,
  distance metric, sparse profile, collection, active generation) with no credential material.
- [x] 5.5 Ensure all settings surfaces are read-only unless an authorized backend write
  endpoint exists; label any writable control clearly.

## 6. Quality, validation, and docs

- [x] 6.1 Add smoke tests for the shell route guard, ingestion flow, streaming consumer, and
  settings panels using the existing vitest setup.
- [x] 6.2 Run `bun run lint` and `bun run typecheck` across `apps/web` and `packages/*`; ensure
  Biome rules pass (no `any`, no `console.*`, `const`, double quotes, no semicolons).
- [x] 6.3 Verify SSE streaming through the BFF proxy (no buffering) and the non-streaming
  fallback.
- [x] 6.4 Run `openspec validate rag-console-ui` and ensure all delta specs pass validation.
- [x] 6.5 Update the project README/docs to describe the console routes and how to run the UI
  locally.