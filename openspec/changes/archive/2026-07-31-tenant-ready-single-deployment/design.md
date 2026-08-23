## Context

The RAG architecture targets an open-source, self-hosted installation using FastAPI,
PostgreSQL, Redis/BullMQ, an S3-compatible object store, and Qdrant. It already
identifies tenant, ACL, ingestion, and retrieval filtering as architectural
boundaries, but no tenant model or enforcement rule exists in the current starter.

The first supported topology is one organization per deployment. The deployment owns
one PostgreSQL database, Redis namespace, object-store prefix/bucket policy, and
Qdrant collection set. The design must preserve that simple operator experience while
making future shared SaaS and dedicated enterprise deployments possible without
rewriting document lineage or retrieval security.

## Goals / Non-Goals

**Goals:**

- Make one deployment tenant a required and verifiable runtime identity.
- Make tenant identity explicit in future PostgreSQL entities, repository contracts,
  HTTP dependencies, ingestion jobs, object keys, cache keys, vector payloads, and
  optional graph projections.
- Ensure callers cannot choose, override, or omit tenant scope.
- Establish testable cross-boundary isolation rules before RAG resources are added.
- Preserve a clear path to shared multi-tenant SaaS or dedicated enterprise stacks.

**Non-Goals:**

- A public tenant-management API, tenant switcher, billing, tenant invitations, or
  cross-tenant administration.
- Running several customer tenants in the same deployment in the first release.
- One Qdrant collection, database, queue service, or API process per tenant.
- PostgreSQL row-level security in the initial single-deployment mode.
- Adding Qdrant, object storage, RAG entities, or ingestion endpoints in this change.

## Decisions

### Deployment identity is configuration-owned and immutable

`DEPLOYMENT_TENANT_ID` is a required UUID-like stable identifier set by the operator
before first startup. The API bootstraps or verifies exactly one matching `tenants`
record. Startup fails if the setting is absent, malformed, disabled, or disagrees with
the persisted deployment tenant. It is never accepted from a browser header, path,
query parameter, request body, or JWT claim.

Changing the ID in place is forbidden. An operator that needs a new tenant identity
must provision a new deployment and migrate/export data deliberately.

Alternatives considered:

- Deriving identity from hostname is fragile across local environments and restores.
- Letting the first authenticated user create a tenant makes bootstrap and recovery
  ambiguous.
- A client-supplied `X-Tenant-ID` would create an avoidable confused-deputy boundary.

### Use an explicit tenant and membership foundation

The future PostgreSQL model starts with `tenants` and `tenant_memberships`.
Authentication resolves the active deployment tenant, then verifies that the current
user has an active membership before granting tenant-scoped access. A user does not
choose a tenant in v1; the deployment context supplies it.

Every tenant-owned resource has a non-null `tenant_id`, including knowledge bases,
connectors, document versions, chunk manifests, ingestion jobs, conversations,
answer traces, citations, feedback, and audit events. Tenant-local uniqueness uses
composite indexes such as `(tenant_id, external_id)`. Parent/child links use composite
foreign keys or tenant equality checks so a child cannot reference another tenant's
parent.

Existing auth users receive membership in the sole deployment tenant through an
additive Alembic migration. The migration must not alter current user IDs, password
hashes, or sessions.

Alternatives considered:

- Adding `tenant_id` only when shared SaaS begins would require broad reindexing and
  document lineage migration.
- Placing a single `tenant_id` directly on `users` prevents a future user membership
  in multiple tenants.
- Creating a separate database per tenant is reserved for dedicated enterprise
  deployments, not the open-source default.

### Tenant context is an application capability, not an optional parameter

FastAPI creates an immutable `TenantContext` from deployment configuration and the
authenticated membership. HTTP routers receive it through dependencies; application
services and repository protocols require it for every tenant-owned operation. No
repository method may provide an unscoped list, retrieval, mutation, or delete API.

Authorization evaluates both tenant membership and resource ACL. Audit events record
the tenant ID, actor ID, action, resource identity, and request/trace ID. Internal
system maintenance operations use an explicitly named maintenance scope and remain
operator-only.

PostgreSQL RLS is deferred because there is only one tenant in a deployment and RLS
adds operational complexity to Alembic, async sessions, and support tooling. The
schema, repository contract, and integration tests are designed so RLS can later be
introduced as defence in depth for a shared deployment.

### Derived stores receive tenant identity as mandatory payload and namespace

Tenant isolation cannot end at PostgreSQL:

| Boundary | Required rule |
| --- | --- |
| Object storage | Key begins `tenants/{tenant_id}/`; raw documents and parser artifacts never share a tenant-neutral key. |
| BullMQ/Redis | Every job payload and idempotency key includes `tenantId`; workers reject a payload inconsistent with the deployment tenant. |
| Cache | Cache key begins with tenant ID and includes the ACL/version dimension when relevant. |
| Qdrant | Each point carries indexed `tenant_id`; every search, scroll, update, and delete uses the matching mandatory payload filter. Collections remain per compatible embedding profile, not per tenant. |
| Optional graph | Nodes and relationships carry `tenant_id`; traversal predicates scope both start nodes and returned paths. |
| Observability | Logs, metrics labels where cardinality allows, traces, evaluation records, and audit events carry tenant identity. |

Object-store paths, queue names, vector IDs, and graph IDs remain deterministic within
tenant scope. Cross-boundary derived data is rebuildable from PostgreSQL manifests and
object storage, never authoritative by itself.

Alternatives considered:

- One Qdrant collection per tenant creates operational sprawl and makes embedding
  profile upgrades expensive.
- Relying on client-side filtering leaks candidates and is prohibited.
- Putting tenant ID only in object paths does not protect vector, queue, or cache data.

### Migration to shared tenancy is intentional, not automatic

A future shared SaaS mode may add a control plane and tenant selection after explicit
product, billing, support, and isolation decisions. It reuses the same tenant IDs,
membership model, payload filters, and composite constraints. Dedicated enterprise
mode instead provisions a separate deployment and sets its deployment tenant ID.

The mode is declared as `single-deployment` in configuration and is included in health
and operator diagnostics. A direct mode switch to shared multi-tenancy is unsupported;
it requires a separate approved migration plan, load tests, backup validation, and
security review.

## Risks / Trade-offs

- [Tenant fields add work before RAG resources exist] → Use reusable context and
  repository contracts once, then require them in each future resource change.
- [A forgotten vector or queue filter could leak data in future shared mode] → Make
  filter construction server-side, require integration tests, and reject unscoped
  adapter methods.
- [Operator misconfigures the deployment tenant ID] → Validate at startup against the
  persisted tenant record and never infer a replacement ID.
- [Membership migration affects current login behavior] → Use additive migrations,
  backfill the single tenant membership transactionally, and contract-test auth.
- [Tenant values increase log/metric cardinality] → Use tenant ID in traces/audits;
  add metric labels only where bounded or aggregated.
- [RLS is not active in v1] → Maintain mandatory application/repository filters and
  document RLS as a future shared-SaaS defence-in-depth change.

## Migration Plan

1. Add the deployment configuration, `tenants`, and `tenant_memberships` model with
   an Alembic revision that creates or verifies the sole tenant.
2. Backfill active memberships for existing users without changing user or session
   identifiers.
3. Add `TenantContext` to FastAPI dependencies, application services, repositories,
   audit utilities, and contract/integration tests.
4. When RAG resource changes begin, add non-null `tenant_id`, composite constraints,
   and scoped adapter tests to each new resource in the same migration.
5. Add tenant namespaces and mandatory filters before enabling object-store, queue,
   Qdrant, or graph adapters.
6. Validate backup/restore in a disposable environment and verify startup fails on a
   mismatched deployment tenant ID.

Rollback before any tenant-owned RAG resources exist is an application rollback plus
the corresponding additive database revision. After data is written, rollback must
preserve the tenant mapping and use a backup/restore plan; the deployment tenant ID
must never be reassigned in place.

## Open Questions

- Should the sole initial tenant record be created by `alembic upgrade`, a dedicated
  operator command, or first application startup after migration?
- Is `DEPLOYMENT_TENANT_ID` sufficient, or should `DEPLOYMENT_TENANT_SLUG` be a
  separate human-readable immutable operator label?
- Which retention and export obligations must the tenant lifecycle support in v1?
- At what scale or regulatory threshold does PostgreSQL RLS become mandatory for the
  shared-SaaS follow-up?
