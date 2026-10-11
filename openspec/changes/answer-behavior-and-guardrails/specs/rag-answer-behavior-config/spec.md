## Purpose

Defines the versioned, server-controlled policy for how final answers are generated,
including persona, output limits, allowed knowledge sources, greetings, and fallback.

## ADDED Requirements

### Requirement: Effective answer behavior is versioned and server-controlled

The system SHALL provide an answer-behavior configuration with an immutable version,
an explicit scope, and an effective timestamp. A knowledge-base override SHALL take
precedence over the deployment default; otherwise the deployment default SHALL apply.
Only an authorized tenant ADMIN SHALL create, update, activate, or retire a
configuration. Query callers MUST NOT override or inject answer-behavior settings.
Every completed query trace MUST identify the effective configuration version.

#### Scenario: Knowledge-base override is selected
- **WHEN** a query targets a knowledge base with an active answer-behavior override
- **THEN** the service applies that override and records its version in the query trace

#### Scenario: Caller attempts to override behavior
- **WHEN** a query payload includes persona, source policy, greeting policy, or token-budget fields
- **THEN** request validation rejects the unsupported fields and the server keeps the effective configuration unchanged

#### Scenario: Non-admin updates a configuration
- **WHEN** a non-admin attempts to create, update, activate, or retire an answer-behavior configuration
- **THEN** the service returns `FORBIDDEN` and makes no configuration change

### Requirement: Persona and response style are bounded and policy subordinate

The configuration SHALL support a bounded administrator-authored persona instruction and
a response-style value from the fixed supported set `CONCISE`, `BALANCED`, or
`DETAILED`. The persona instruction MUST be
treated as lower priority than immutable safety, tenant, source-policy, citation, and
output-validation rules. Persona text MUST NOT be allowed to request hidden reasoning,
secrets, policy bypass, or unsupported source claims.

#### Scenario: Valid persona is applied
- **WHEN** an active configuration contains a valid persona and response style
- **THEN** the final generation request includes them and the released answer follows them when no higher-priority policy conflicts

#### Scenario: Persona attempts to weaken policy
- **WHEN** an administrator-authored persona instructs the model to ignore citations or reveal protected content
- **THEN** configuration validation rejects it or the immutable policy layer overrides it before generation

### Requirement: Output token budgets are bounded and provider-neutral

The configuration SHALL expose `max_output_tokens` with a default of 1024 and an
accepted range of 128 through the deployment maximum, whose default MUST be 8192.
The effective budget MUST be clamped or rejected before provider invocation, passed to
every supported generation provider, and recorded with the effective provider/model
configuration. A provider that cannot honor the budget MUST fail safely rather than
silently using an unbounded default.

#### Scenario: Valid output budget is used
- **WHEN** an administrator saves `max_output_tokens=2048` and a query is generated
- **THEN** the provider request uses a budget no greater than 2048 and the trace records the effective budget

#### Scenario: Output budget exceeds the deployment maximum
- **WHEN** an administrator submits a value greater than the deployment maximum
- **THEN** the configuration is rejected with a validation error and no active version is changed

#### Scenario: Provider cannot enforce the budget
- **WHEN** a provider adapter cannot apply the effective output budget
- **THEN** the query returns a safe operational failure and MUST NOT release an answer as if the budget were enforced

### Requirement: Source policy explicitly controls answer provenance

The configuration SHALL support these source policies:

- `DOCUMENT_ONLY`: factual and inferential claims MUST be supported by selected authorized document evidence; no general-knowledge answer is allowed.
- `DOCUMENT_OR_MCP`: claims MAY use selected authorized document evidence or validated MCP evidence; general-knowledge-only claims are not allowed.
- `DOCUMENT_MCP_GENERAL`: safe general-knowledge answers are allowed when no allowed source supports the claim, but the answer MUST be marked non-grounded and MUST NOT fabricate citations.

The service MUST apply the policy before generation and again before release. A source
policy MUST NOT be weakened by planner output, retrieved text, MCP output, conversation
history, memory, or client input.

#### Scenario: Document-only query has no evidence
- **WHEN** `DOCUMENT_ONLY` is active and retrieval returns no valid document evidence
- **THEN** the service follows the configured no-evidence action and does not generate an ungrounded factual answer

#### Scenario: Document-or-MCP query has valid MCP evidence
- **WHEN** `DOCUMENT_OR_MCP` is active and an allowed MCP invocation returns validated provenance
- **THEN** the service may generate an answer supported by that MCP evidence and exposes its provenance

#### Scenario: General knowledge is allowed
- **WHEN** `DOCUMENT_MCP_GENERAL` is active and no selected source supports a safe request
- **THEN** the service may answer generally, returns empty document citations, and marks the result as non-grounded

### Requirement: Greeting behavior is explicit and independent

The configuration SHALL support `ALLOW_UNGROUNDED`, `REQUIRE_ALLOWED_SOURCE`, and
`REFUSE` greeting policies. Greeting handling MUST use the same admission, guardrail,
tenant, and output-validation pipeline as other queries. The system MUST NOT require a
hard-coded phrase list or a greeting-specific route.

#### Scenario: Greetings are allowed without source evidence
- **WHEN** `ALLOW_UNGROUNDED` is active and the user submits a safe greeting
- **THEN** the normal generation path may return a non-grounded answer without fabricated citations

#### Scenario: Greetings require an allowed source
- **WHEN** `REQUIRE_ALLOWED_SOURCE` is active and the greeting has no valid document or MCP evidence
- **THEN** the service returns the configured safe no-evidence outcome without generating a general answer

#### Scenario: Greeting policy refuses
- **WHEN** `REFUSE` is active and the user submits a greeting
- **THEN** the service returns a safe refusal outcome without answer content

### Requirement: No-evidence fallback is explicit and compatible

The configuration SHALL define a no-evidence action of `ABSTAIN`, `REFUSE`, or
`ANSWER_UNGROUNDED`. `ANSWER_UNGROUNDED` MUST be invalid unless the source policy
allows general knowledge. Existing deployments SHALL receive a recorded migrated
default so behavior is reproducible rather than dependent on hard-coded code paths.

#### Scenario: Invalid fallback combination
- **WHEN** an administrator selects `ANSWER_UNGROUNDED` with `DOCUMENT_ONLY`
- **THEN** configuration validation rejects the combination

#### Scenario: Migrated deployment default
- **WHEN** the change is deployed to an existing tenant without an explicit configuration
- **THEN** migration creates an active versioned default and records its source and effective policy
