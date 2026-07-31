# Tenant Deployment Guide

This document explains single-deployment tenant mode, bootstrap, configuration
validation, backup/restore expectations, and migration paths for the RAG
platform.

## Single-Deployment Tenant Mode

The first supported topology is **one organization per deployment**. The
deployment owns one PostgreSQL database, Redis namespace, object-store
prefix, and Qdrant collection set. This keeps setup and operations simple
while preserving a clear path to shared multi-tenancy later.

### Configuration

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `DEPLOYMENT_TENANT_ID` | **yes** | none | Stable UUID identifier for the deployment tenant. Set before first startup. |
| `TENANT_MODE` | no | `single-deployment` | Only `single-deployment` is supported in v1. |

The `DEPLOYMENT_TENANT_ID` must be a valid UUID string. It is validated at
config-load time and verified against the persisted tenant record at startup.

### Bootstrap

1. Set `DEPLOYMENT_TENANT_ID` to a new UUID in `apps/api/.env`.
2. Run database migrations:

   ```bash
   bun run db:upgrade
   ```

3. Start the API. The application lifespan verifies the deployment tenant:
   - If no tenant record exists, it creates one with the configured ID.
   - If a tenant record exists and matches, startup proceeds.
   - If a tenant record exists but does **not** match, startup fails.

4. Existing users automatically receive an active membership in the sole
   deployment tenant through an idempotent backfill at startup. User IDs,
   password hashes, and auth-session identifiers are never modified.

### Operator Diagnostics

The `/health` endpoint includes tenant diagnostics:

```json
{
  "data": {
    "status": "ok",
    "tenant": {
      "tenantMode": "single-deployment",
      "deploymentTenantId": "<uuid>",
      "tenantId": "<uuid>",
      "tenantSlug": "deployment-<prefix>",
      "tenantName": "Deployment Tenant",
      "membershipsBackfilled": 0,
      "supportedModes": ["single-deployment"]
    }
  }
}
```

### What is NOT Accepted

- **No client tenant selection.** The tenant identity is never accepted from
  a browser header (`X-Tenant-ID`), path, query parameter, request body, or
  JWT claim.
- **No tenant switcher UI.** Users do not choose a tenant; the deployment
  context supplies it.
- **No public tenant provisioning API.** Tenant management is operator-only.
- **No cross-tenant search.** Each deployment serves exactly one tenant.

## Immutability

The `DEPLOYMENT_TENANT_ID` is **immutable for the life of a deployment**.
Changing it in place is forbidden. If an operator starts an existing
deployment with a different configured tenant ID, startup is rejected and no
data is reassigned.

### Why Immutable?

- Reassigning a tenant ID in place would break object-store keys, Qdrant
  payload filters, cache keys, and graph node identifiers that embed the old
  tenant ID.
- It would create ambiguity about data ownership and audit lineage.
- A deliberate migration/export procedure is safer than an in-place change.

### How to Change Tenant Identity

1. Provision a new deployment with the new `DEPLOYMENT_TENANT_ID`.
2. Export data from the old deployment.
3. Import data into the new deployment, mapping old tenant IDs to the new one.
4. Validate backup/restore in a disposable environment before switching.

## Backup and Restore

### PostgreSQL

- Back up the database using `pg_dump` or a managed snapshot.
- The `tenants` and `tenant_memberships` tables are part of the standard
  backup — no special handling is required.
- On restore, the `DEPLOYMENT_TENANT_ID` in the environment **must match**
  the `id` column in the restored `tenants` table. If it does not, startup
  will fail.

### Object Store

- Back up the `tenants/{tenant_id}/` prefix.
- On restore, verify the object-store prefix matches the deployment tenant ID.

### Qdrant

- Qdrant is a derived projection — it can be rebuilt from PostgreSQL + object
  store. No tenant-aware backup is required beyond the source-of-truth backup.

## Validation

Startup fails if:

| Condition | Error Code | HTTP Status |
| --- | --- | --- |
| `DEPLOYMENT_TENANT_ID` is not set | `TENANT_NOT_CONFIGURED` | 500 |
| `DEPLOYMENT_TENANT_ID` is not a valid UUID | pydantic validation error | — |
| Configured ID does not match persisted tenant | `TENANT_MISMATCH` | 500 |
| An active tenant exists with a different ID | `TENANT_MISMATCH` | 500 |
| `TENANT_MODE` is not `single-deployment` | pydantic validation error | — |