## Why

The console currently presents Planner, Decomposition, Memory, and Answer Policy as
Knowledge Base settings even though one assistant project may use several Knowledge Bases.
That makes the same chatbot behavior appear fragmented and can produce conflicting runtime
configuration when a query searches multiple KBs. A first-class Project boundary is needed
so a chatbot such as “Chatbot A” can consistently use KBs such as “SOP Karyawan” and
“SOP Return” under one shared runtime policy.

## What Changes

- Add a tenant-scoped Project entity and console workspace.
- Allow one Project to contain many Knowledge Bases; each Knowledge Base belongs to exactly one Project.
- Move Planner, Decomposition, Memory configuration, Answer Policy, and Guardrails to Project scope.
- Keep documents, ingestion, parser/chunking, embedding, indexing, sync, and retrieval diagnostics at Knowledge Base scope.
- Make query execution resolve one Project context for all selected Knowledge Bases and reject cross-Project selections.
- Add Project and Knowledge Base membership APIs with tenant isolation and ADMIN-only writes.
- Migrate existing Knowledge Bases into tenant default Projects without silently deleting legacy configuration.
- Retain legacy Knowledge Base configuration reads for a bounded compatibility period, while making new writes Project-scoped.
- Move the console navigation and detail tabs to `/console/projects`; remove orchestration tabs from Knowledge Base detail.
- Update shared schemas, response types, OpenAPI, audit events, traces, tests, and operational documentation.

## Capabilities

### New Capabilities

- `rag-project-workspace`: Tenant-scoped Projects, one-to-many Knowledge Base membership, Project APIs, query scope, migration, and Project console surfaces.

### Modified Capabilities

- `rag-query-task-planner`: Planner configuration and its settings UI move from Knowledge Base scope to Project scope.
- `rag-query-decomposition`: Decomposition configuration is managed at Project scope while remaining opt-in and evaluation-gated.

## Impact

- **API/domain**: new Project entity, membership validation, project-scoped configuration repositories/services, query request scope validation, authorization, and audit metadata.
- **Database**: Project table, Knowledge Base `project_id`, project-scoped configuration columns/constraints, migration/backfill, and compatibility indexes.
- **Web**: new Project list/detail routes, moved settings tabs, Project-to-KB management, legacy-route handling, and query project context.
- **Contracts**: Pydantic, Zod, shared response types, API constants, query keys, OpenAPI, and trace metadata.
- **Operations**: migration/rollback runbook and explicit detection of KBs with legacy settings that require administrator review.
