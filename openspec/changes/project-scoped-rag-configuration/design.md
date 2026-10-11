## Context

The repository currently has no Project aggregate. Knowledge Bases are tenant-scoped and
the Planner, Decomposition, Memory, and the newly added Answer Policy/Guardrails surfaces
persist configuration by `knowledge_base_id`. Ingestion and document lifecycle are also
KB-scoped. The change therefore crosses domain identity, persistence, query admission,
configuration services, API contracts, and the console hierarchy. See `proposal.md` and
the delta specs for the observable contract.

## Goals / Non-Goals

**Goals:**

- Establish a tenant-safe one-to-many Project → Knowledge Base ownership model.
- Apply one effective orchestration, memory, answer, and safety configuration to all KBs in a Project.
- Preserve KB data-plane isolation and document/index lineage.
- Migrate existing tenants idempotently and make legacy configuration reviewable.
- Make cross-Project queries fail closed before downstream side effects.
- Provide a coherent Project console and contract-first API surface.

**Non-Goals:**

- Sharing one Knowledge Base between Projects; this design deliberately uses one owner Project per KB.
- Merging documents, vector collections, ACLs, or ingestion pipelines across KBs.
- Allowing end users to choose or mutate policy, planner, or guardrail configuration per request.
- Removing legacy records immediately or silently rewriting their historical audit data.
- Moving provider credentials, deployment-wide model settings, or raw document operations into Project scope.

## Decisions

### 1. Use a one-to-many ownership model

Add a Project aggregate and a required `project_id` on Knowledge Base after a staged
backfill. A join table was rejected because shared KBs would make a selected KB set
ambiguous: the same KB could inherit different policies depending on the Project. The
chosen model makes membership, authorization, effective policy, and query traces
deterministic. Moving a KB is an explicit ADMIN operation and is audited.

### 2. Resolve Project before any query side effects

The query request may carry `project_id`, but the server remains authoritative. When it is
omitted, the server infers the Project only if all selected KBs have the same owner. A
Project mismatch or non-member KB returns a stable validation error before planner,
retrieval, MCP, memory scheduling, or generation starts. The resolved Project id is passed
through synchronous, streaming, and async query paths and recorded in traces.

### 3. Store moved configuration at Project scope and keep a compatibility read path

New Planner, Decomposition, Memory, Answer Policy, and Guardrail records use `project_id`
and project-level uniqueness/versioning. Existing KB records are retained as legacy data;
their new writes are disabled. During the compatibility period, a legacy read can return
the owning Project configuration plus explicit deprecation metadata. Query resolution uses
the Project profile as authoritative; a single-KB query may consult a legacy KB profile only
when no Project profile exists and the compatibility flag permits it. Multi-KB queries never
merge conflicting legacy profiles.

### 4. Separate control-plane and data-plane UI ownership

Project detail owns the shared control-plane tabs: Planner, Decomposition, Answer Policy,
Guardrails, and Memory. Knowledge Base detail owns data-plane tabs: Documents, Ingestion,
Parser/chunking, Embedding/Indexing, Sync, and Diagnostics. A single reusable settings
component receives a Project target rather than duplicating forms for each KB.

### 5. Migrate conservatively

The migration creates one deterministic default Project per tenant, assigns unassigned
active KBs, and leaves document/index rows untouched. It does not pick a winner when
legacy configuration differs; it records a review item and relies on the deployment/tenant
default until an administrator saves a Project profile. A feature flag controls whether the
legacy single-KB fallback remains active, and the compatibility end date is explicit in
operations documentation.

### 6. Treat configuration moves as auditable state changes

Project membership changes, Project configuration writes, legacy fallback use, migration
review items, and cross-Project query rejections receive stable audit/reason codes. The
audit payload contains identifiers and bounded metadata only; it never stores credentials,
raw provider arguments, or unbounded prompts/source payloads.

### 7. Prefer additive API rollout

Introduce `/rag/projects` and `/rag/projects/{project_id}/...` routes first. Keep old
Knowledge Base read routes as compatibility shims, then deprecate them with response
metadata and metrics before removal. This permits the existing console and external
clients to upgrade without a flag day while preventing new KB-scoped configuration writes.

## Risks / Trade-offs

- **[Risk] Existing KBs have conflicting local configuration** → Preserve all legacy records, create a migration review item, use a safe default rather than silently selecting one, and expose the conflict to administrators.
- **[Risk] Moving a KB changes chatbot behavior** → Require ADMIN authorization, show the destination Project and effective configuration before commit, audit the move, and include the Project id in traces.
- **[Risk] Cross-Project query selection breaks existing clients** → Infer the Project for unambiguous selections, expose a stable error for ambiguous selections, and update shared clients/console before enforcement.
- **[Risk] Project policy is accidentally weakened by a KB setting** → Make Project records authoritative, reject new KB-scoped writes, and test precedence plus tenant isolation at the service boundary.
- **[Risk] Migration partially succeeds** → Use transactional per-tenant backfill, idempotency keys/unique constraints, a preflight report, and a resumable repair command; never downgrade shared data destructively.

## Migration Plan

1. Add Project tables, staged `project_id` column/indexes, migration review records, and audit reason codes.
2. Backfill one default Project per tenant and assign active KBs transactionally; leave the column nullable until preflight confirms full coverage.
3. Add Project APIs and project-scoped config records/services while keeping legacy reads and writes behind a compatibility flag.
4. Update query admission and all sync/stream/async workers to resolve and trace one Project.
5. Ship the Project console, move shared tabs, update external/shared contracts, and emit deprecation telemetry for legacy URLs.
6. Disable legacy KB writes, then legacy single-KB fallback after the documented review window and confirmation that all tenants have Project profiles.
7. Roll back application enforcement by re-enabling the compatibility flag; retain Project/membership/audit rows and do not downgrade migrations in production.

## Open Questions

None. The ownership cardinality, query conflict behavior, migration safety policy, and
compatibility strategy are resolved for implementation.
