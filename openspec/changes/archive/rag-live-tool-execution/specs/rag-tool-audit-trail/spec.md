# rag-tool-audit-trail Specification (delta)

## Purpose
Define the append-only audit trail that records every tool invocation — permitted or
denied — with enough tamper-detectable information for operators to investigate
incidents without exposing raw query parameters or tool outputs.

## ADDED Requirements

### Requirement: Every tool dispatch attempt is recorded
The system SHALL write one `tool_audit_log` entry for every tool dispatch attempt,
regardless of outcome. DENIED, TIMEOUT, ERROR, and SUCCESS outcomes MUST all produce
an audit entry. An entry MUST be written before the tool result is returned to the
caller.

#### Scenario: Tool is denied before dispatch
- **WHEN** the permission check denies a tool for the tenant
- **THEN** a DENIED audit entry is written with tenant_id, tool_definition_id,
  trace_id, query_id, input_hash, and status = DENIED before continuing

#### Scenario: Tool executes successfully
- **WHEN** a tool adapter returns a result within timeout and size limits
- **THEN** a SUCCESS audit entry is written with input_hash, output_hash, latency_ms,
  and status = SUCCESS

### Requirement: Audit entries record hashes, not raw content
The system SHALL record SHA-256 hashes of the serialized tool input and output in
`tool_audit_log`. Raw input and raw output values MUST NOT be stored in the audit
table. The audit table MUST NOT contain provider credentials, PII derived from tool
output, or cross-tenant data.

#### Scenario: Operator inspects the audit log
- **WHEN** an operator queries the tool_audit_log for a tenant
- **THEN** each entry contains input_hash, output_hash (or NULL on error), latency_ms,
  status, and error_message without raw input, raw output, or credential values

### Requirement: Audit log is append-only and tenant-scoped
The system SHALL not permit UPDATE or DELETE on `tool_audit_log` rows. All reads MUST
be scoped to the authenticated tenant. Audit entries for one tenant MUST NOT be
accessible by another tenant or by unauthenticated requests.

#### Scenario: Audit log query crosses tenant boundary
- **WHEN** a request attempts to read audit entries for a tenant_id outside the
  authenticated scope
- **THEN** the system returns 403 and performs no read

### Requirement: Audit trail propagates trace context
The system SHALL include the originating `trace_id` and `query_id` in every audit
entry. Security-relevant outcomes (DENIED, TIMEOUT, ERROR) MUST also be emitted to
the platform trace/log infrastructure so operators can correlate tool audit entries
with request traces without querying the audit table directly.

#### Scenario: Tool execution fails and operator investigates
- **WHEN** an operator searches trace infrastructure for a failed query
- **THEN** the trace contains the tool slug, audit status, and latency alongside the
  query trace without requiring a separate audit table query
