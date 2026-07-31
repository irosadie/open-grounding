## ADDED Requirements

### Requirement: Tenant context is server-derived and mandatory
The system SHALL create immutable tenant context from deployment configuration and
authenticated membership. HTTP routers, application services, and repositories MUST
require this context for every tenant-owned operation.

#### Scenario: Authenticated member accesses a tenant-owned resource
- **WHEN** an authenticated user with active membership makes a tenant-owned request
- **THEN** the server derives the active deployment tenant context and uses it for
  authorization and data access

#### Scenario: Client attempts to override tenant scope
- **WHEN** a request includes a tenant ID in a header, path, query, body, or token
  claim that conflicts with the deployment tenant
- **THEN** the server ignores the client-supplied value and does not access another
  tenant's data

### Requirement: Tenant-owned records have non-null ownership and local integrity
The system SHALL persist a non-null `tenant_id` for every tenant-owned resource.
Tenant-local uniqueness and parent-child relationships MUST prevent a resource from
being associated with a parent belonging to another tenant.

#### Scenario: Cross-tenant parent reference is attempted
- **WHEN** an application attempts to create or update a tenant-owned child with a
  parent from another tenant
- **THEN** the persistence operation is rejected and no cross-tenant association is
  stored

### Requirement: Repositories never expose unscoped tenant-owned operations
The system SHALL expose tenant context as a required repository contract parameter for
tenant-owned reads, writes, lists, searches, and deletes. Repository implementations
MUST apply the tenant constraint in the database operation itself.

#### Scenario: Repository lists tenant-owned records
- **WHEN** an application service requests a tenant-owned list using tenant context
- **THEN** the repository returns only records whose `tenant_id` matches that context

### Requirement: Tenant access is auditable
The system SHALL record tenant ID, actor ID when available, action, resource identity,
and request or trace ID for tenant-owned mutations and security-relevant denials.

#### Scenario: Access is denied for missing membership
- **WHEN** an authenticated user lacks active membership in the deployment tenant
- **THEN** the request is denied before resource access and an audit event records the
  tenant, actor, denial action, and trace identity
