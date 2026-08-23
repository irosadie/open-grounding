## ADDED Requirements

### Requirement: Readiness dashboard surfaces dependency health without secrets

The settings console SHALL display the platform readiness reported by `/ready`, distinguishing
PostgreSQL, Redis, Qdrant, object storage, deployment tenant, and active index-profile
availability. It MUST NOT expose credentials, internal URLs, or raw provider error payloads,
and MUST mark the overall status as ready or degraded.

#### Scenario: A dependency is unavailable

- **WHEN** readiness reports an unavailable dependency
- **THEN** the UI shows that dependency as unavailable and the overall status as degraded
  without displaying any secret or internal URL

### Requirement: Tenant context is displayed as server-derived and read-only

The settings console SHALL display the tenant context returned by `/auth/tenant/context`
(tenant id, membership id, user id) as read-only. It MUST NOT allow the user to edit or
override the tenant, membership, or user identity, and MUST NOT accept a client-supplied
tenant value to change the displayed context.

#### Scenario: User views tenant context

- **WHEN** an authenticated user opens the settings tenant panel
- **THEN** the UI shows the server-derived tenant, membership, and user identity as read-only
  and offers no control to override them

### Requirement: Knowledge bases are listed within tenant scope

The settings console SHALL list knowledge bases scoped to the server-derived tenant using the
existing success envelope. It MUST NOT display knowledge bases from another tenant and MUST
show each knowledge base's lifecycle metadata and policy boundary as reported by the catalog.

#### Scenario: User browses knowledge bases

- **WHEN** an authenticated user opens the settings knowledge-base panel
- **THEN** the UI lists only knowledge bases authorized for the active tenant with their
  metadata and does not expose another tenant's catalog

### Requirement: Model and index profiles are shown without credential material

The settings console SHALL display model and index profile metadata (provider references,
vector dimensions, distance metric, sparse profile, collection identity, and active generation)
as read-only. It MUST NOT display provider credential values and MUST mark profiles that are
incompatible or inactive accordingly.

#### Scenario: User inspects an index profile

- **WHEN** an authenticated user opens a profile panel
- **THEN** the UI shows the profile's non-secret compatibility metadata and active generation
  status without returning any credential material

### Requirement: Configuration is read-only unless a backend write endpoint exists

The settings console SHALL render all configuration surfaces as read-only by default. It MUST
NOT present an editable control for a value the backend does not accept writes for, and any
write control MUST call an existing, authorized backend endpoint through the BFF proxy.

#### Scenario: User views a read-only configuration

- **WHEN** a user opens a configuration surface for which no backend write endpoint exists
- **THEN** the UI presents the value as read-only and provides no edit control, avoiding any
  implication that a write is possible