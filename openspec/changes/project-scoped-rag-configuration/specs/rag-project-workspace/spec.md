## Purpose

Defines the tenant-scoped Project boundary that groups Knowledge Bases and owns the
shared query, answer, memory, and safety configuration for a chatbot workspace.

## ADDED Requirements

### Requirement: A Project groups Knowledge Bases within one tenant

The system SHALL provide a tenant-scoped Project resource with a stable identifier,
name, slug, lifecycle status, and audit timestamps. A Project MAY contain many active
Knowledge Bases, and each Knowledge Base SHALL belong to exactly one active Project.
Project and membership reads MUST be restricted to the caller's server-derived tenant.
Only an authorized tenant ADMIN SHALL create, rename, archive, or move a Knowledge Base
between Projects.

#### Scenario: Administrator creates a Project with multiple Knowledge Bases
- **WHEN** an authorized tenant ADMIN creates a Project and assigns two or more authorized Knowledge Bases
- **THEN** the Project is created and each assigned Knowledge Base is shown as a member of that Project

#### Scenario: User reads another tenant's Project
- **WHEN** a caller requests a Project or Knowledge Base membership using an identifier owned by another tenant
- **THEN** the API returns the standard not-found or forbidden response without revealing resource existence

#### Scenario: Non-admin changes Project membership
- **WHEN** a non-admin attempts to create, archive, rename, or move a Knowledge Base between Projects
- **THEN** the API returns `FORBIDDEN` and no membership or Project metadata changes

#### Scenario: Administrator moves a Knowledge Base
- **WHEN** an authorized tenant ADMIN moves an active Knowledge Base to another active Project in the same tenant
- **THEN** the membership changes atomically, the move is audited, and subsequent queries resolve the new Project configuration

### Requirement: Project-scoped runtime configuration is authoritative

Planner, decomposition, memory configuration, answer behavior, and guardrails SHALL be
managed at Project scope and SHALL apply consistently to every Knowledge Base in that
Project. Project configuration writes SHALL create the same immutable/versioned records
and audit events required by the corresponding capability. New configuration writes MUST
NOT accept a Knowledge Base identifier as the policy owner.

#### Scenario: Project configuration applies to several Knowledge Bases
- **WHEN** a Project contains “SOP Karyawan” and “SOP Return” and an administrator saves an Answer Policy
- **THEN** queries against either KB, or both together, use the same effective Project Answer Policy version

#### Scenario: Project settings are read by an authorized member
- **WHEN** an authenticated tenant member opens a Project configuration surface
- **THEN** the service returns the effective Project configuration and its inheritance/source metadata without exposing secrets

#### Scenario: A legacy Knowledge Base write is attempted
- **WHEN** a client attempts to create or update Planner, Decomposition, Memory, Answer Policy, or Guardrails through a Knowledge Base-scoped write endpoint after the compatibility window is disabled
- **THEN** the API rejects the write with a documented deprecation or validation error and does not create a KB-scoped override

### Requirement: Query execution has one unambiguous Project context

Every query that selects Knowledge Bases SHALL resolve one Project context from an explicit
Project identifier or from the selected KB memberships. If an explicit Project is supplied,
every selected Knowledge Base MUST belong to that Project. If no Project is supplied, the
server MAY infer it only when all selected Knowledge Bases belong to the same Project.
Cross-Project selections and invalid memberships SHALL fail closed with a stable validation
reason before planner, retrieval, memory, MCP, or generation work begins.

#### Scenario: Query searches several KBs in one Project
- **WHEN** a query selects “SOP Karyawan” and “SOP Return” from the same Project
- **THEN** the query resolves one Project context and applies one Planner, Decomposition, Memory, Answer Policy, and Guardrails configuration

#### Scenario: Query selects KBs from different Projects
- **WHEN** a query selects Knowledge Bases that belong to different Projects
- **THEN** validation returns a stable Project-scope conflict and no downstream query task is executed

#### Scenario: Explicit Project contains an unauthorized KB
- **WHEN** a query supplies a Project identifier together with a Knowledge Base that is not a member of that Project
- **THEN** validation rejects the request without disclosing cross-tenant or cross-Project details

#### Scenario: Query trace records Project scope
- **WHEN** a query completes, abstains, refuses, or fails operationally
- **THEN** its trace and response metadata identify the resolved Project, selected KB identifiers, and effective configuration versions when available

### Requirement: Knowledge Base data-plane settings remain Knowledge Base scoped

Documents, source connectors, ingestion settings, parser and chunking settings, embedding
and indexing settings, synchronization state, and retrieval diagnostics SHALL remain owned by
the Knowledge Base. Project membership SHALL NOT merge document stores or alter the identity,
ACL, lifecycle, or index lineage of a Knowledge Base.

#### Scenario: Project contains separate document stores
- **WHEN** a Project contains two Knowledge Bases with different documents and ingestion settings
- **THEN** a query may retrieve from both while preserving each document's KB identity, ACL, citation, and ingestion metadata

#### Scenario: KB ingestion setting is changed
- **WHEN** an administrator updates ingestion settings for one Knowledge Base
- **THEN** only that KB's ingestion behavior changes and Project-level response/orchestration configuration remains unchanged

### Requirement: Existing Knowledge Bases migrate without silent data loss

The migration SHALL create an active default Project for each existing tenant that lacks a
Project, assign every existing active Knowledge Base to exactly one Project, and preserve
all existing documents, indexes, ACLs, and audit history. Existing Knowledge Base-scoped
configuration records SHALL remain readable as explicitly marked legacy records until the
documented compatibility period ends. The migration MUST be idempotent and MUST report any
legacy configurations that cannot be represented by one Project profile without silently
discarding them.

#### Scenario: Existing tenant is migrated
- **WHEN** the migration runs for a tenant with active Knowledge Bases and no Project
- **THEN** one default Project is created, all active KBs are assigned exactly once, and document/index counts remain unchanged

#### Scenario: Migration runs twice
- **WHEN** the same migration is executed again after a successful run
- **THEN** it makes no duplicate Project or membership records and reports the existing mapping as already migrated

#### Scenario: Legacy profiles conflict
- **WHEN** two KBs in a migrated tenant have different active legacy Planner or Answer Policy profiles
- **THEN** the migration preserves both legacy records, records a review item, and does not silently select one as the Project policy

### Requirement: Project console navigation reflects ownership

The console SHALL provide a Project list and Project detail workspace. Project detail SHALL
expose Overview, Knowledge Bases, Planner, Decomposition, Answer Policy (including Guardrails),
and Memory. Knowledge Base detail SHALL expose data-plane surfaces such as Documents and
Ingestion Settings and SHALL NOT present Project-owned settings as if they were KB-owned.
Legacy deep links SHALL redirect to the owning Project surface when ownership is unambiguous,
or show a read-only migration message with the required next action.

#### Scenario: User opens a Project workspace
- **WHEN** an authenticated user opens a Project containing several Knowledge Bases
- **THEN** the console shows the member KBs and the shared Planner, Decomposition, Answer Policy, Guardrails, and Memory settings

#### Scenario: User opens Knowledge Base detail
- **WHEN** an authenticated user opens a KB detail page
- **THEN** the console shows KB data-plane settings and links to its owning Project without duplicating Project configuration forms

#### Scenario: User follows a legacy policy link
- **WHEN** a user opens a previous KB Answer Policy URL for a KB with an unambiguous Project owner
- **THEN** the console redirects to that Project's Answer Policy surface and preserves the intended navigation context

### Requirement: Project APIs expose safe, versioned contracts

The service SHALL expose tenant-scoped Project list/detail/membership operations and
Project-scoped configuration endpoints for each moved capability. API responses SHALL use
stable Project and Knowledge Base identifiers, effective/inherited source metadata, and
documented error codes. OpenAPI, shared schemas, response types, query keys, and audit
events SHALL describe the same contract. Responses MUST NOT expose provider credentials,
raw prompts that are classified secret, or cross-tenant resource details.

#### Scenario: Frontend loads Project configuration
- **WHEN** the console requests a Project and its configuration
- **THEN** the response validates against the shared contract and identifies the Project owner and member KBs

#### Scenario: API contract is generated
- **WHEN** OpenAPI is exported after the change
- **THEN** Project routes, request fields, response fields, and stable error responses are present and schema validation passes
