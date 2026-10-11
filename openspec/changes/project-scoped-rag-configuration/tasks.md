## 1. Project domain and persistence

- [x] 1.1 Add the tenant-scoped Project entity, lifecycle states, ownership invariants, and stable domain errors; verify unit tests cover active/archived projects and one-owner-per-KB rules.
- [x] 1.2 Add Project and Knowledge Base project-membership persistence models, indexes, constraints, and tenant-scoped repositories; verify repository tests reject cross-tenant access.
- [x] 1.3 Add the migration review/audit model and explicit compatibility feature settings; verify migration metadata cannot contain secrets or unbounded payloads.
- [x] 1.4 Write the staged Alembic migration for Projects, `knowledge_base.project_id`, backfill support, and project-scope indexes; verify upgrade, idempotent rerun, and safe downgrade behavior in an isolated database.
- [x] 1.5 Implement idempotent tenant backfill and legacy-conflict reporting; verify existing documents, indexes, ACLs, and historical policy rows are unchanged.

## 2. Project and membership API

- [x] 2.1 Add Project list/create/detail/update/archive schemas and service methods with ADMIN-only mutations; verify authorized reads and forbidden writes.
- [x] 2.2 Add Knowledge Base assignment/move operations with same-tenant and active-Project validation; verify the membership update is atomic and audited.
- [x] 2.3 Add Project routes, stable error responses, and response metadata for membership and migration review state; verify OpenAPI route coverage.
- [x] 2.4 Update Knowledge Base create/list/detail contracts to expose the owning Project and enforce the chosen assignment/default behavior; verify legacy KBs are represented correctly.

## 3. Project-scoped configuration

- [x] 3.1 Add project ownership and repository methods to Planner and Decomposition configuration; verify one active Project configuration is resolved for every member KB.
- [x] 3.2 Move Memory configuration reads/writes to Project scope while preserving user-memory data isolation; verify project config applies to all member KBs.
- [x] 3.3 Extend Answer Policy and Guardrails persistence, resolver, audit events, and endpoints with Project scope; verify Project precedence, immutable versions, and legacy read metadata.
- [x] 3.4 Disable new KB-scoped writes for moved settings and implement the bounded compatibility read path; verify the feature flag controls single-KB fallback and multi-KB conflicts are never merged.
- [x] 3.5 Add project-level effective-configuration endpoints and defaults for all moved capabilities; verify responses identify source, version, Project, and affected KBs without secrets.

## 4. Query and worker integration

- [x] 4.1 Add optional `project_id` to synchronous, streaming, and async query contracts and propagate it through routes, workers, and task plans; verify contract parity.
- [x] 4.2 Implement server-side Project inference and membership validation before planner/retrieval/MCP/memory/generation side effects; verify cross-Project queries fail closed.
- [x] 4.3 Update effective Planner, Decomposition, Memory, Answer Policy, and Guardrails resolution to use the resolved Project; verify a multi-KB query has one effective version per moved configuration.
- [x] 4.4 Add Project identifiers, membership, configuration versions, and conflict reason codes to traces, SSE completion metadata, async results, and audit events; verify redaction and stable serialization.
- [x] 4.5 Add regression tests for one-KB inference, multi-KB same-Project queries, explicit Project mismatch, cross-tenant IDs, archived Projects, and legacy fallback.

## 5. Console and shared contracts

- [x] 5.1 Add shared Project schemas, enums, response types, API routers, query keys, and contract tests; verify Zod/Pydantic/OpenAPI parity.
- [x] 5.2 Add Project list/detail routes and Project-to-KB management UI with loading, empty, forbidden, migration-review, and error states; verify only tenant-authorized Projects and KBs render.
- [x] 5.3 Move Planner, Decomposition, Answer Policy/Guardrails, and Memory tabs into Project detail using reusable Project-targeted settings components; verify ADMIN controls and read-only states.
- [x] 5.4 Remove Project-owned configuration editors from Knowledge Base detail and retain only data-plane surfaces; verify Ingestion Settings remains KB-scoped.
- [x] 5.5 Add legacy KB deep-link redirects/read-only migration messaging and global Projects navigation; verify old URLs do not create KB-level writes.
- [x] 5.6 Update query UI to select a Project and only its member KBs, while preserving a safe inferred path for existing requests; verify cross-Project selections cannot be submitted.

## 6. Documentation, OpenAPI, and operations

- [x] 6.1 Export and validate OpenAPI with Project and moved configuration routes; verify generated docs match shared response contracts.
- [x] 6.2 Update console, query, migration, rollback, and compatibility runbooks; verify the compatibility end date and review procedure are explicit.
- [x] 6.3 Add metrics for Project resolution, cross-Project rejection, legacy fallback, migration conflicts, and Project membership moves; verify dimensions are tenant-safe and bounded.

## 7. Verification and rollout

- [x] 7.1 Run backend unit, integration, migration, authorization, and query pipeline tests; verify tenant isolation and no downstream side effects on rejected scope.
- [x] 7.2 Run frontend tests, shared contract tests, type checks, lint/format checks, and route smoke tests; verify Project and KB navigation ownership.
- [x] 7.3 Run full OpenAPI export/validation, migration preflight on a representative snapshot, and strict OpenSpec validation; verify all artifacts and implementation contracts are consistent.
- [x] 7.4 Perform a production-readiness review of rollback, legacy compatibility, audit retention, and data preservation; verify the rollout can be paused without destructive downgrade.

### Verification follow-ups completed

- Migration preflight and downgrade rehearsal passed against an isolated representative snapshot.
- Full repository lint and typecheck passed after resolving the existing formatting findings.
- Production-readiness sign-off covers compatibility-window closure, audit retention, data preservation, and rollback ownership.
