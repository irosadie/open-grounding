## Why

The open-source RAG platform needs strong organization-level isolation without making
the first self-hosted deployment as complex as a shared SaaS platform. Starting with
one tenant per deployment keeps setup, operations, and data ownership simple while
avoiding a costly data-model migration when shared multi-tenancy or dedicated
enterprise deployments are added later.

## What Changes

- Define a deployment tenant as a required, immutable runtime identity for one
  FastAPI, PostgreSQL, Redis, object-store, and vector-index deployment.
- Introduce a tenant context and tenant-scoped persistence contract for future
  knowledge bases, documents, ingestion jobs, chunks, conversations, audit events,
  and RAG retrieval traces.
- Require tenant identity to be enforced server-side at HTTP, application,
  PostgreSQL, object-store, queue, and vector/graph projection boundaries.
- Define tenant lifecycle and operator configuration, including safe bootstrap,
  validation, backup/restore, and a future migration path to shared multi-tenancy.
- Keep the initial release single-tenant per deployment: no tenant selection UI,
  public tenant provisioning API, billing, cross-tenant search, or shared SaaS
  control plane is added.

## Capabilities

### New Capabilities

- `single-deployment-tenant-mode`: Establish one immutable active tenant for each
  self-hosted deployment and expose safe operator lifecycle rules.
- `tenant-context-and-isolation`: Define tenant-scoped data, request context,
  authorization, and audit requirements across the FastAPI application.
- `tenant-aware-rag-boundaries`: Define isolation requirements for object storage,
  BullMQ jobs, Qdrant payloads, optional graph projections, and retrieval filters.

### Modified Capabilities

None. No main OpenSpec capability specifications exist yet.

## Impact

- Future FastAPI domain models, SQLAlchemy mappings, Alembic migrations, repository
  protocols, and HTTP dependencies will carry tenant context.
- Future RAG services must scope object keys, queue payloads, Qdrant filters, and
  optional graph queries by tenant identity.
- Deployment configuration gains a deployment-tenant identifier and validation
  rules; PostgreSQL, Redis, BullMQ, and the Node worker remain shared runtime
  components inside a single tenant deployment.
- The architecture in `docs/RAG-ARCHITECTURE.md` becomes the implementation
  reference; this change does not add Qdrant, object storage, or RAG endpoints yet.
