## ADDED Requirements

### Requirement: Live tool execution is sandboxed, permitted, and audited
The system SHALL allow the query planner to call external tools, web search, database,
or transactional systems only under a per-tenant permission model, an execution
sandbox, and a per-tenant audit trail. It MUST NOT execute a tool without explicit
permission scope and MUST NOT make tool output part of long-term memory.

#### Scenario: Tool call is not permitted for the tenant
- **WHEN** the planner selects a tool that the tenant has not explicitly permitted
- **THEN** the system declines the tool call and continues with the default grounded
  evidence path without executing it
