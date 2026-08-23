# single-deployment-tenant-mode Specification

## Purpose
TBD - created by archiving change tenant-ready-single-deployment. Update Purpose after archive.
## Requirements
### Requirement: Deployment has exactly one active tenant identity
The system SHALL require a stable deployment tenant identity before serving
tenant-owned functionality. The identity MUST be configured by the operator, MUST
match exactly one active persisted tenant record, and MUST NOT be accepted from a
client request or token claim.

#### Scenario: Valid single-tenant startup
- **WHEN** the configured deployment tenant ID matches one active tenant record
- **THEN** the application starts in `single-deployment` tenant mode and exposes the
  active mode through operator diagnostics

#### Scenario: Missing or mismatched tenant identity
- **WHEN** the tenant setting is absent, invalid, disabled, or does not match the
  persisted deployment tenant record
- **THEN** the application fails startup without serving tenant-owned requests

### Requirement: Deployment tenant identity is immutable in place
The system SHALL treat the configured deployment tenant identity as immutable for the
life of a deployment. An operator MUST provision a separate deployment and use an
explicit migration/export procedure to adopt a different tenant identity.

#### Scenario: Operator changes the configured tenant ID
- **WHEN** an existing deployment starts with a different configured tenant ID
- **THEN** startup is rejected and no data is reassigned to the new tenant ID

### Requirement: Existing users belong to the deployment tenant
The system SHALL maintain tenant membership separately from user identity. Existing
active users MUST receive an active membership in the sole deployment tenant through
an additive migration without changing user IDs, password hashes, or auth-session
identifiers.

#### Scenario: Existing user authenticates after tenant bootstrap
- **WHEN** a user created before the tenant foundation authenticates after migration
- **THEN** the user retains the existing identity and can access only through the
  active deployment tenant membership

