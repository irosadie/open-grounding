# rag-tool-permission Specification (delta)

## Purpose
Define the per-tenant explicit allow-list that gates every tool dispatch. No tool may
be called unless it appears in the tenant's permission table and is active. Denials are
recorded in the audit log.

## ADDED Requirements

### Requirement: Tool execution requires explicit tenant permission
The system SHALL maintain a `tenant_tool_permission` table as the authoritative
allow-list. A tool MUST NOT be dispatched unless the tenant has an active permission
record for that tool definition. The permission check MUST occur before enqueueing the
BullMQ task.

#### Scenario: Planner selects a tool not permitted for the tenant
- **WHEN** the query planner selects a tool whose slug is absent from the tenant's
  permission allow-list
- **THEN** the system records a DENIED entry in `tool_audit_log`, skips the tool, and
  continues with the remaining permitted tools or falls back to the `grounded` route

#### Scenario: All selected tools are denied
- **WHEN** every tool selected by the planner is denied or inactive for the tenant
- **THEN** the system falls back to the `grounded` evidence route without returning
  an error to the client

### Requirement: Permission grants record operator identity and time
The system SHALL record the granting operator's user ID and the grant timestamp in
`tenant_tool_permission`. Permission records MUST NOT be deleted; they are logically
revoked by an `is_revoked` flag and a `revoked_at` timestamp.

#### Scenario: Operator revokes a previously granted permission
- **WHEN** an operator revokes a tool permission for a tenant
- **THEN** the permission record is marked `is_revoked = true` with `revoked_at`
  set to the current time, and the tool is no longer dispatched for that tenant

### Requirement: Permission model does not expose cross-tenant data
The system SHALL scope all permission reads and writes strictly to the authenticated
tenant context. An operator MUST NOT be able to grant, revoke, or inspect permissions
belonging to a different tenant.

#### Scenario: Operator requests permissions for another tenant
- **WHEN** an operator query includes a tenant_id not matching their authenticated scope
- **THEN** the system returns 403 and performs no read or write
