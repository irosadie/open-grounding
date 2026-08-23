# Tenant Migration Paths

This document describes the future migration paths from single-deployment
mode to shared-SaaS and dedicated-enterprise topologies, including deferred
PostgreSQL RLS and containerization decisions.

## Current State: Single-Deployment

The platform currently runs in `single-deployment` tenant mode:

- One deployment = one tenant = one organization.
- PostgreSQL, Redis, BullMQ, object store, and Qdrant are shared runtime
  components inside a single tenant deployment.
- Tenant identity is enforced at the application and repository layer.
- PostgreSQL row-level security (RLS) is **not** active.

## Future Path 1: Shared SaaS

A shared SaaS mode may serve multiple customer tenants from a single
deployment. This requires:

1. **Control plane**: A tenant management API, tenant switcher, billing,
   support, and isolation decisions.
2. **Tenant selection**: Authenticated users select or are assigned a tenant
   from their memberships. The `TenantContext` dependency already supports
   this — it would resolve the selected tenant instead of the deployment
   tenant.
3. **PostgreSQL RLS**: Row-level security becomes a defence-in-depth layer
   on top of the existing application/repository filters. Each table gains
   a `tenant_id` RLS policy. This is deferred for v1 because:
   - Application-level filtering is already mandatory and tested.
   - RLS adds operational complexity and debugging difficulty.
   - The single-deployment mode has no cross-tenant risk.
4. **Object-store isolation**: Per-tenant buckets or stricter prefix policies.
5. **Qdrant isolation**: The mandatory tenant payload filter (already in
   place) becomes critical. Collection-per-tenant is optional but creates
   operational sprawl.
6. **Metric cardinality**: Tenant ID labels must be bounded or aggregated to
   avoid unbounded cardinality.

### Reused Components

The shared-SaaS path reuses the same:
- Tenant IDs and membership model.
- `TenantContext` and FastAPI dependencies.
- `TenantNamespace` key/filter primitives.
- `TenantRepository` protocols with mandatory `tenant_id` parameters.
- Composite constraints (`tenant_id`, `user_id`) and indexes.
- Audit events with tenant ID, actor ID, and trace correlation.

### Migration Steps

1. Approve a separate migration plan with product, billing, support, and
   security decisions.
2. Add the control plane and tenant selection flow.
3. Enable PostgreSQL RLS policies on all tenant-owned tables.
4. Run load tests and backup validation.
5. Conduct a security review.
6. Deploy with a feature flag, rolling out tenant-by-tenant.

**A direct mode switch from `single-deployment` to shared multi-tenancy is
unsupported.** It requires the steps above.

## Future Path 2: Dedicated Enterprise

A dedicated enterprise deployment provisions a **separate deployment** for
each customer. Each deployment sets its own `DEPLOYMENT_TENANT_ID` and runs
its own PostgreSQL, Redis, object store, and Qdrant instance.

This path is simpler than shared SaaS:

1. No control plane is needed — each deployment is independent.
2. No RLS is needed — isolation is physical, not logical.
3. The same `TenantContext`, `TenantNamespace`, and repository contracts
   apply unchanged.
4. Operations scale horizontally with the number of deployments.

### Trade-offs

| Aspect | Shared SaaS | Dedicated Enterprise |
| --- | --- | --- |
| Isolation | logical (RLS + app filters) | physical (separate stacks) |
| Cost efficiency | high (shared resources) | lower (dedicated resources) |
| Operational complexity | high (control plane, RLS) | moderate (more deployments) |
| Blast radius | shared (config bug affects all) | isolated (per-deployment) |
| Tenant onboarding | fast (API call) | slow (provision deployment) |

## Deferred Decisions

### PostgreSQL Row-Level Security

RLS is deferred for v1 because:
- The single-deployment mode has no cross-tenant risk.
- Application/repository filters are already mandatory and integration-tested.
- RLS adds operational complexity without immediate benefit.
- It will be revisited as a defence-in-depth change for the shared-SaaS path.

### Containerization

A deployable Python container image for the FastAPI API is deferred to a
dedicated containerization change. Local development and CI run the API
through `uv`; PostgreSQL and Redis remain in the shared Compose service.

### In-Place Tenant ID Change

Changing `DEPLOYMENT_TENANT_ID` in place is **never supported**. Object-store
keys, Qdrant payload filters, cache keys, and graph node identifiers embed
the tenant ID. An in-place change would break isolation and audit lineage.
Operators must provision a new deployment and migrate/export data.