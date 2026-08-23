# Tasks: rag-live-tool-execution

## 1. Database schema

- [x] 1.1 Write SQLAlchemy ORM model for `tool_definition` (id, tenant_id, slug, version, schema JSONB, adapter TEXT, is_active, created_at).
- [x] 1.2 Write SQLAlchemy ORM model for `tenant_tool_permission` (id, tenant_id, tool_definition_id, granted_at, granted_by, is_revoked, revoked_at).
- [x] 1.3 Write SQLAlchemy ORM model for `tool_audit_log` (id, tenant_id, tool_definition_id, trace_id, query_id, input_hash, output_hash, latency_ms, status, error_message, created_at).
- [x] 1.4 Generate Alembic migration for the three tables; verify it applies cleanly on a fresh DB.
- [x] 1.5 Add DB-level constraint: only one active version per (tenant_id, slug) — partial unique index on `is_active = true`.

## 2. Domain layer

- [x] 2.1 Add `ToolDefinition` domain entity with slug, version, adapter, input_schema, output_schema, is_active.
- [x] 2.2 Add `ToolPermission` domain entity with granted_by, is_revoked.
- [x] 2.3 Add `ToolAuditEntry` domain entity with input_hash, output_hash, latency_ms, status (enum: SUCCESS / TIMEOUT / ERROR / DENIED), error_message.
- [x] 2.4 Add `ToolAuditStatus` enum to `packages/schemas/` (SCREAMING_SNAKE_CASE: SUCCESS, TIMEOUT, ERROR, DENIED).
- [x] 2.5 Define `IToolDefinitionRepository` protocol: `get_active(tenant_id, slug)`, `list_active(tenant_id)`, `save(definition)`, `deactivate_previous(tenant_id, slug)`.
- [x] 2.6 Define `IToolPermissionRepository` protocol: `is_permitted(tenant_id, slug)`, `grant(permission)`, `revoke(tenant_id, slug, revoked_by)`, `list(tenant_id)`.
- [x] 2.7 Define `IToolAuditRepository` protocol: `append(entry)`, `list(tenant_id, filters)`. Define `IToolAuditRepository` protocol: `append(entry)`, `list(tenant_id, filters)`.

## 3. Infrastructure layer

- [x] 3.1 Implement `SqlToolDefinitionRepository` (async SQLAlchemy) for `IToolDefinitionRepository`.
- [x] 3.2 Implement `SqlToolPermissionRepository` (async SQLAlchemy) for `IToolPermissionRepository`; enforce tenant scope on all reads/writes.
- [x] 3.3 Implement `SqlToolAuditRepository` (async SQLAlchemy) for `IToolAuditRepository`; no UPDATE/DELETE — append-only enforced at application layer.
- [x] 3.4 Add `ToolAdapter` abstract base class: `async def execute(input: dict) -> dict`.
- [x] 3.5 Implement first built-in `WebSearchToolAdapter` (stub returning empty results) behind the abstract base.
- [x] 3.6 Implement `AdapterRegistry`: loads adapter class by name from a configured registry at worker startup; raises `AdapterNotFoundError` on unknown name. Implement `AdapterRegistry`: loads adapter class by name from a configured registry at worker startup; raises `AdapterNotFoundError` on unknown name.

## 4. Application layer — tool routing and dispatch

- [x] 4.1 Add `ToolRouteSelector` use case: given tenant_ctx and candidate tool slugs, check `IToolPermissionRepository`, return permitted tools, write DENIED audit entries for rejected ones.
- [x] 4.2 Add `ToolDispatcher` use case: enqueue BullMQ job via worker client, await result within `timeout_ms + buffer`, handle TIMEOUT and ERROR by writing audit entry and raising domain error.
- [x] 4.3 Add `ToolEvidenceNormalizer` use case: parse raw output against tool schema, produce `ToolEvidence[]` items (source_type="tool", citation_id="tool:{slug}:{i}").
- [x] 4.4 Extend `QueryPlannerService` to recognize `tool` route: only select when tenant has at least one permitted active tool AND intent classifier scores a tool match; fall back to `grounded` on empty permitted set.
- [ ] 4.5 Wire `ToolRouteSelector` → `ToolDispatcher` → `ToolEvidenceNormalizer` into the query execution path before the generation pipeline. NOTE: Requires adding `QueryRoute.TOOL` to domain enum, implementing tool intent classifier, and extending `_query_admitted` in `rag_query_service.py`. Deferred to next iteration — all supporting components (selector, dispatcher, normalizer) are implemented and tested.

## 5. Worker layer — BullMQ ToolExecutionProcessor

- [x] 5.1 Add `ToolExecutionProcessor` to `apps/worker/src/`: loads `AdapterRegistry`, resolves adapter by slug, runs `asyncio.wait_for(adapter.execute(input), timeout_ms)`.
- [x] 5.2 Enforce `max_output_bytes` cap: measure raw output size before returning; write ERROR audit entry and raise if exceeded.
- [x] 5.3 Catch all unhandled adapter exceptions: write ERROR audit entry, mark job failed, do not crash worker process.
- [x] 5.4 Ensure job payload contains no secrets: validate that tenant context in job payload has only tenant_id, trace_id, tool_slug, input dict.
- [x] 5.5 Register `ToolExecutionProcessor` in the worker queue registry. Register `ToolExecutionProcessor` in the worker queue registry.

## 6. HTTP interface layer

- [x] 6.1 Add `POST /tools` endpoint (operator only): accepts tool definition body, validates JSON Schema fields, calls `SaveToolDefinition` use case, returns 201.
- [x] 6.2 Add `GET /tools` endpoint (operator only): lists active tool definitions for the authenticated tenant.
- [x] 6.3 Add `POST /tools/{slug}/permissions` endpoint (operator only): grant tool permission for tenant; record granted_by from auth context.
- [x] 6.4 Add `DELETE /tools/{slug}/permissions` endpoint (operator only): revoke permission; set is_revoked=true, revoked_at=now.
- [x] 6.5 Add `GET /tools/audit` endpoint (operator only): list audit entries for authenticated tenant with pagination; enforce tenant scope.
- [x] 6.6 Add Pydantic DTOs: `ToolDefinitionRequest`, `ToolDefinitionResponse`, `ToolPermissionResponse`, `ToolAuditEntryResponse`.
- [x] 6.7 Verify all new endpoints return 403 when tenant scope mismatch is detected. Verify all new endpoints return 403 when tenant scope mismatch is detected.

## 7. SSE stream extension

- [x] 7.1 Add `tool_call` SSE event type: emits `{ tool_slug, input_hash, trace_id }` after permission check passes, before dispatch.
- [x] 7.2 Add `tool_result` SSE event type: emits `{ tool_slug, evidence_count, latency_ms, status }` after dispatch completes.
- [x] 7.3 Verify neither event emits raw input, raw output, credentials, or cross-tenant metadata. Verify neither event emits raw input, raw output, credentials, or cross-tenant metadata.

## 8. OpenAPI

- [x] 8.1 Annotate all new endpoints with tags, summaries, response_model, and error responses.
- [x] 8.2 Export updated `docs/openapi.json` via `openspec docs export` or equivalent. Export updated `docs/openapi.json` via `openspec docs export` or equivalent.

## 9. Tests

- [x] 9.1 Unit test `ToolRouteSelector`: permitted tool passes, denied tool writes DENIED audit entry and is excluded.
- [x] 9.2 Unit test `ToolDispatcher`: timeout triggers TIMEOUT audit entry; success path returns raw output.
- [x] 9.3 Unit test `ToolEvidenceNormalizer`: valid output produces correct `ToolEvidence[]` with expected citation IDs.
- [x] 9.4 Unit test `SqlToolAuditRepository`: verify no UPDATE/DELETE methods exist; append writes correct row.
- [x] 9.5 Unit test `ToolExecutionProcessor`: adapter exception is caught, ERROR audit written, worker continues.
- [ ] 9.6 Integration test: full query with `tool` route — permission check → dispatch → evidence normalize → generation → SSE stream includes `tool_call` and `tool_result` events.
- [ ] 9.7 Integration test: all tools denied → fallback to `grounded` route, no error returned to client.
- [ ] 9.8 Integration test: tool exceeds timeout → TIMEOUT audit entry written, query continues on grounded fallback. Integration test: tool exceeds timeout → TIMEOUT audit entry written, query continues on grounded fallback.

## 10. Deferred tracker update

- [x] 10.1 Mark task 2.2 in `openspec/changes/rag-query-deferred-followups/tasks.md` as complete.

## 11. Console UI — Tool Config

- [x] 11.1 Add `tools` nav item to `apps/web/configs/console.ts` with `indent: true` and `href: "/console/settings/tools"`.
- [x] 11.2 Add Zod schemas to `packages/schemas/`: `toolDefinitionSchema`, `toolPermissionSchema`, `toolAuditEntrySchema`.
- [x] 11.3 Add response types to `packages/types/`: `ToolDefinitionResponse`, `ToolPermissionResponse`, `ToolAuditEntryResponse`.
- [x] 11.4 Add API route constants to `apps/web/constants/api-routers.ts` under `rag.tools`.
- [x] 11.5 Add query keys to `apps/web/constants/query-keys.ts` under `tools`.
- [x] 11.6 Write hook `apps/web/hooks/transactions/use-tools/index.ts`.
- [x] 11.7 Create `apps/web/app/console/settings/tools/page.tsx`.
- [x] 11.8 Create `apps/web/app/console/settings/tools/tools-content.tsx`.
- [x] 11.9 Inline registration form with Zod validation.
- [x] 11.10 Permissions section with Grant button and inline Revoke confirm.
- [x] 11.11 Audit log section with status badges, read-only.
- [x] 11.12 Status badges following console convention.
- [x] 11.13 Verify page renders within console sidebar layout. Verify page renders correctly within console sidebar layout and sidebar highlights Tools nav item as active.
