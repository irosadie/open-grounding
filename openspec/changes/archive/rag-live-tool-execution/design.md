# Design: rag-live-tool-execution

## Context

`rag-grounded-query` ships a single evidence path: vector + sparse hybrid retrieval
from pre-ingested Qdrant chunks. Five capabilities were explicitly deferred. This change
implements the second deferred item — Live Tool Execution — which was gated on three
conditions: (1) a sandbox, (2) a per-tenant permission model, and (3) an audit trail.

All three gating conditions are addressed here. The default `grounded` path is
unchanged. The `tool` route is additive and OFF unless the tenant has explicitly
permitted at least one tool.

## Goals / Non-Goals

**Goals:**

- Add a `tool` query route to the planner alongside `grounded`, `clarify`, `abstain`.
- Define a tool registry: versioned tool definitions stored per tenant in the catalog.
- Enforce a per-tenant explicit permission allow-list before every dispatch.
- Execute tools outside the FastAPI request process (BullMQ worker task) with a
  per-call timeout and output size cap.
- Normalize tool output to `ToolEvidence` and feed it into the existing generation
  and validation pipeline with no special-casing.
- Record a full audit entry per tool invocation (input hash, output hash, latency,
  status) in an append-only `tool_audit_log` table.
- Extend SSE stream with `tool_call` and `tool_result` events.
- Mark task 2.2 in `rag-query-deferred-followups` as implementable.

**Non-Goals:**

- Multi-step tool chaining or agentic loops.
- Tool output stored in Qdrant or long-term memory.
- Tool authoring or management UI.
- Outbound calls from inside the FastAPI web process.
- Numeric confidence calibration or graph retrieval (separate deferred changes).

## Architecture

### New layers

```
Query Request
  → QueryPlannerService          (existing — extended with tool route)
      └→ ToolRouteSelector       (new — checks tenant permission, selects tools)
          └→ ToolDispatcher      (new — enqueues BullMQ task, awaits result)
              └→ BullMQ Worker   (existing worker — new ToolExecutionProcessor)
                  └→ ToolAdapter (new — per-tool isolated executor)
  → ToolEvidenceNormalizer       (new — converts raw output → ToolEvidence[])
  → existing generation pipeline (unchanged — ToolEvidence treated as document chunk)
  → ToolAuditLogger              (new — writes append-only audit entry)
```

### Tool Registry (catalog layer)

A `tool_definition` table stores versioned, tenant-scoped tool definitions:

```
tool_definition
  id          UUID PK
  tenant_id   UUID FK
  slug        TEXT           -- stable identifier, e.g. "web-search"
  version     INT
  schema      JSONB          -- JSON Schema for input/output
  adapter     TEXT           -- adapter class name, loaded at worker startup
  is_active   BOOLEAN
  created_at  TIMESTAMPTZ
```

A `tenant_tool_permission` table is the explicit allow-list:

```
tenant_tool_permission
  id              UUID PK
  tenant_id       UUID FK
  tool_definition_id UUID FK
  granted_at      TIMESTAMPTZ
  granted_by      UUID         -- operator user id
```

A `tool_audit_log` table is the append-only audit trail:

```
tool_audit_log
  id              UUID PK
  tenant_id       UUID FK
  tool_definition_id UUID FK
  trace_id        TEXT
  query_id        UUID
  input_hash      TEXT         -- SHA-256 of serialized input
  output_hash     TEXT         -- SHA-256 of serialized output, NULL on error
  latency_ms      INT
  status          TEXT         -- SUCCESS | TIMEOUT | ERROR | DENIED
  error_message   TEXT         -- NULL on SUCCESS
  created_at      TIMESTAMPTZ
```

### Permission check (before every dispatch)

```
ToolRouteSelector.select(tenant_ctx, selected_tools[]) → permitted_tools[]
  for each tool in selected_tools:
    if tool.slug NOT IN tenant_tool_permission(tenant_id): → DENIED, audit entry
    if tool.is_active = false: → DENIED, audit entry
  return permitted_tools (may be empty → fallback to grounded route)
```

If `permitted_tools` is empty after filtering, the planner falls back to `grounded`
without returning an error to the client.

### Execution sandbox (BullMQ worker)

```
ToolDispatcher.dispatch(tool, input, tenant_ctx, trace_id)
  → enqueue BullMQ job: { tool_slug, input, tenant_id, trace_id, timeout_ms, max_output_bytes }
  → await result with timeout_ms + buffer
  → on TIMEOUT: write audit TIMEOUT, raise ToolTimeoutError
  → on ERROR: write audit ERROR, raise ToolExecutionError
  → on SUCCESS: write audit SUCCESS, return raw_output
```

Worker-side `ToolExecutionProcessor`:
- Loads `ToolAdapter` by `adapter` class name from registry.
- Enforces `timeout_ms` via `asyncio.wait_for`.
- Enforces `max_output_bytes` on raw output before returning.
- Never passes tenant credentials to tool input; tool adapter reads from env/config.

### Evidence normalization

```
ToolEvidenceNormalizer.normalize(tool, raw_output, trace_id) → ToolEvidence[]
  → parse raw_output against tool.schema
  → for each result item:
      ToolEvidence(
        source_type = "tool",
        tool_slug   = tool.slug,
        tool_version= tool.version,
        content     = item.text,
        metadata    = { trace_id, retrieved_at, tool_slug },
        citation_id = f"tool:{tool.slug}:{i}"
      )
```

`ToolEvidence` satisfies the same `Evidence` protocol as document chunks — no changes
to the generation or validation pipeline.

### SSE extension

Two new event types added to the existing SSE stream:

```
event: tool_call
data: { tool_slug, input_hash, trace_id }

event: tool_result
data: { tool_slug, evidence_count, latency_ms, status }
```

`input_hash` is emitted (not raw input) to avoid leaking query parameters to the
client stream. Raw input is only in the audit log.

### Query planner route extension

`QueryRoute` enum gains a new value: `tool`. Route selection logic:

```
if tenant has permitted tools AND query intent matches tool capability:
    route = tool
elif evidence threshold met:
    route = grounded
elif query is ambiguous:
    route = clarify
else:
    route = abstain
```

The `tool` route is only selected when the planner's intent classifier scores a tool
match AND the tenant has at least one permitted, active tool. Both conditions must hold.

## Decisions

### Tools execute in BullMQ worker, not in the FastAPI request process

Keeps the web process safe from blocking, runaway, or crashing tool calls. Timeouts
are enforced at the worker level. Worker already exists in `apps/worker/`.

### Tool output is ephemeral evidence, not memory

Tool output is normalized to `ToolEvidence[]` and treated identically to document
chunks by the generation pipeline. It is never written to Qdrant, never added to
conversation memory, and never persisted beyond the query lifecycle.

### Audit log records hashes, not raw values

`input_hash` and `output_hash` (SHA-256) give operators a tamper-detectable record
without storing potentially sensitive query parameters or tool responses in the audit
table. Full content is available in trace/log infrastructure if needed.

### Permission check is synchronous catalog read, not a policy engine

A simple explicit allow-list in the catalog is sufficient for this release and keeps
the gating condition concrete and auditable. A policy engine can be layered later.

### Fallback to `grounded` on empty permitted tools

If the planner selects `tool` but all candidate tools are denied, the system silently
falls back to `grounded` and continues. The denial is recorded in the audit log. The
client sees a normal grounded answer without an error.

## Risks / Trade-offs

- [Tool adapter bugs can cause query latency spikes] → timeout_ms cap enforced at
  worker; client SSE timeout is unchanged.
- [Audit log grows unbounded] → append-only table; operators must schedule periodic
  archiving. A retention policy is outside this change's scope.
- [Intent classifier false-positive triggers tool route unexpectedly] → fallback to
  grounded on empty permitted set; test with golden query set before enabling per tenant.
- [SHA-256 hashes leak input length] → acceptable for audit purposes; full input only
  in trace infrastructure, not the audit table.

## Open Questions

- What `timeout_ms` and `max_output_bytes` defaults are appropriate for the first
  built-in tools (web search, SQL read-only)?
- Should `tool_call` SSE event be suppressible by client preference (some callers may
  not want intermediate events)?
- Does the intent classifier run as part of the planner or as a separate service call?
