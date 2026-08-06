# Proposal: rag-live-tool-execution

## Problem

The current RAG query path is evidence-only: every answer is grounded exclusively in
pre-ingested document chunks from Qdrant. This works well for static knowledge bases
but fails for queries that require live, time-sensitive, or transactional data — stock
prices, weather, database lookups, external APIs, or system state that changes faster
than ingestion cadence allows.

Without a controlled tool-execution path, the system has two bad options:
1. Abstain on any query that needs live data (degrades utility).
2. Hallucinate a plausible but stale answer (degrades trust).

## Proposed Solution

Add a **Live Tool Execution** capability to the query planner. When a query is routed to
the `tool` path (a new route alongside `grounded`, `clarify`, `abstain`), the planner
selects and calls one or more tools from a tenant-permitted registry, collects their
outputs as structured evidence, merges that evidence into the existing generation
pipeline, and emits a full audit trail — all within the same SSE streaming interface
the client already uses.

The capability is OFF by default. It activates only when:
- The tenant has explicitly permitted one or more tools.
- The query planner selects the `tool` route (not `grounded`).
- Every selected tool is within the tenant's permitted set.

Tool output is treated as short-lived ephemeral evidence: it is cited in the answer
like a document chunk, it flows through the same validation and repair pipeline, and it
is NEVER added to long-term memory or the vector index.

## Scope

**In scope:**
- Tool registry: define, register, and version tools per tenant.
- Permission model: per-tenant explicit allow-list, stored in catalog.
- Execution sandbox: timeout, output size cap, error isolation per tool call.
- Audit trail: every tool invocation — input, output hash, latency, result status —
  recorded in a per-tenant audit log with full trace context.
- Query planner route extension: `tool` route added alongside existing routes.
- Evidence merge: tool outputs normalized to `ToolEvidence` and fed into existing
  generation pipeline.
- SSE extension: `tool_call` and `tool_result` events in the existing stream.
- Console UI: `/console/settings/tools` page for tool registration, permission
  management, and audit log inspection — following the existing console settings pattern.

**Out of scope:**
- Multi-tool orchestration / agent loops (more than one sequential tool call per query).
- Tool output added to vector index or long-term memory.
- Outbound network calls from inside the web process (tools run as isolated
  subprocess/worker task via BullMQ or a side-car executor).
- Numeric confidence calibration (separate deferred change).
- Graph retrieval (separate deferred change).

## Gating Conditions (from deferred spec)

This change was deferred from `rag-grounded-query` pending:
1. A sandbox model — defined here as: per-call timeout + output size cap + error
   isolation, executed outside the FastAPI request process via BullMQ worker task.
2. A per-tenant permission model — defined here as: explicit allow-list stored in
   the tenant catalog, checked before every tool dispatch.
3. An audit trail — defined here as: append-only `tool_audit_log` table with tenant,
   trace, tool, input hash, output hash, latency, status; never exposes raw input/output
   to the query response.

All three gating conditions are addressed by this change.

## Non-Goals

- Replace the default `grounded` evidence path.
- Allow tools to override tenant or ACL scope.
- Store tool output beyond the lifetime of a single query.
- Implement agentic loops, planning trees, or multi-step tool chains.
- Provide a UI for tool management (API-only in this release).
