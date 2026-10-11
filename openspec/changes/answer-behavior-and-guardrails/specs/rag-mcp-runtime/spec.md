## ADDED Requirements

### Requirement: MCP results used for answers are provenance-aware

When an effective source policy permits MCP support, a successful tool result used in
answer generation SHALL carry a stable provenance reference containing tenant, server,
tool, invocation, trace, timestamp, and bounded freshness metadata. The result MUST be
associated with the current query and MUST NOT be treated as answer evidence when the
invocation was denied, timed out, failed, stale, or outside the tenant scope.

#### Scenario: Successful MCP result becomes answer evidence
- **WHEN** an allowed MCP invocation succeeds within the current query
- **THEN** the answer context contains a bounded provenance reference that can be validated and displayed to the user

#### Scenario: Failed MCP result is returned to the planner
- **WHEN** an MCP invocation fails, times out, or is denied
- **THEN** its result is not eligible as answer evidence and the query follows the active source-policy fallback

### Requirement: MCP provenance remains untrusted source data

MCP result text SHALL be isolated as untrusted source data. It MUST NOT modify system
instructions, guardrails, authorization, source policy, tool permissions, or citation
rules. Raw credentials, raw arguments, hidden prompts, and unbounded result bodies MUST
NOT be copied into answer traces or client responses.

#### Scenario: MCP result contains prompt-injection text
- **WHEN** a tool result contains instructions to ignore policy or reveal protected data
- **THEN** the result is treated as data, the policy remains unchanged, and any unsafe generated output is blocked

### Requirement: MCP evidence has bounded freshness and payload semantics

Every MCP source policy SHALL define or inherit a maximum result payload and freshness
window. A result outside those bounds MUST be marked stale or unavailable and MUST NOT
support a grounded claim. The answer response SHALL expose safe provenance metadata rather
than internal credentials or connection details.

#### Scenario: MCP result is stale
- **WHEN** a tool result is older than the effective freshness window
- **THEN** the result is excluded from grounded evidence and the query follows the configured fallback
