# rag-tool-registry Specification (delta)

## Purpose
Define versioned, tenant-scoped tool definitions that the query planner can select
and the execution sandbox can load. Each tool has a stable slug, a JSON Schema for
input/output, and an adapter reference loaded at worker startup.

## ADDED Requirements

### Requirement: Tool definitions are versioned and tenant-scoped
The system SHALL store tool definitions in a `tool_definition` catalog table with a
stable slug, version number, JSON Schema for input and output, adapter class reference,
active flag, and tenant ownership. A tool slug MAY have multiple versions but only one
active version per tenant at any time.

#### Scenario: Operator registers a new tool version
- **WHEN** an operator creates a new version of an existing tool slug for a tenant
- **THEN** the previous version is deactivated and only the new version is returned
  by the registry for that tenant

#### Scenario: Tool definition references an unknown adapter
- **WHEN** the worker starts and cannot load the adapter class named in a tool definition
- **THEN** the worker logs the error, marks the tool as inactive, and continues
  processing other tools without crashing

### Requirement: Tool schema is validated before registration
The system SHALL validate that the tool's input and output JSON Schema are well-formed
and that the adapter class name is non-empty before persisting the definition. A
malformed schema MUST be rejected with a validation error.

#### Scenario: Operator submits a tool definition with an invalid JSON Schema
- **WHEN** an operator POST request includes a malformed JSON Schema in the tool body
- **THEN** the API returns 422 and the definition is not persisted

### Requirement: Tool registry is read-only at query time
The system SHALL load permitted tool definitions from the catalog read-path only.
The query planner and dispatcher MUST NOT modify tool definitions or permission records
during query execution.

#### Scenario: Query planner reads tool definitions
- **WHEN** the query planner resolves permitted tools for a tenant during a query
- **THEN** it reads from the catalog without performing any write operation
