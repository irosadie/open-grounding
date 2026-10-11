## MODIFIED Requirements

### Requirement: Query admission and route selection are bounded

The system SHALL enforce configured rate, token, payload, concurrency, knowledge-base,
effective answer-behavior, guardrail, and policy checks before retrieval, generation,
MCP execution, or memory side effects. It MUST route a request only to the supported
grounded, answered, clarify, abstain, or refused outcomes. The effective source policy
and no-evidence action MUST determine whether a request without valid evidence is
answered, abstained, or refused. Query rewriting and validation repair MUST remain
bounded by their configured limits.

#### Scenario: Strict policy has no authorized evidence path
- **WHEN** a query uses `DOCUMENT_ONLY` or `DOCUMENT_OR_MCP` and no permitted evidence is available
- **THEN** the service returns the configured safe abstain or refusal outcome without releasing a general-knowledge answer

#### Scenario: Query lacks an authorized evidence path
- **WHEN** a query has no authorized knowledge base or violates configured policy
- **THEN** the system returns a clarification or abstention outcome without invoking
  retrieval or generation

#### Scenario: General policy has no source evidence
- **WHEN** a query uses `DOCUMENT_MCP_GENERAL`, passes guardrails, and no permitted source supports it
- **THEN** the service may return an `answered` non-grounded outcome without document or fabricated MCP citations

#### Scenario: Client attempts to override source or guardrail policy
- **WHEN** a query payload attempts to select a source policy, disable guardrails, or change the fallback
- **THEN** the server rejects the unsupported override and applies the effective server-side configuration

## ADDED Requirements

### Requirement: Effective policy is applied consistently across query execution paths

The system SHALL apply the same effective answer behavior, guardrail profile, source
policy, and provenance rules to synchronous, streaming, asynchronous, planner-enabled,
planner-disabled, and fallback executions. A planner MUST NOT introduce a task type or
source that the effective policy disallows.

#### Scenario: Planner emits a disallowed GENERAL task
- **WHEN** the effective source policy disallows general knowledge and the planner emits a `GENERAL` task
- **THEN** the task is denied or skipped and cannot contribute answer evidence or supplementary support

#### Scenario: Streaming and blocking paths use the same policy
- **WHEN** the same request is executed once with streaming and once without streaming
- **THEN** both paths apply identical policy decisions, provenance validation, and final route semantics

### Requirement: Greetings follow effective policy without a special route

The system MUST NOT use a hard-coded greeting phrase list or greeting-specific execution
route. A greeting SHALL pass through normal admission and guardrail evaluation, then be
handled according to the effective greeting policy and source policy.

#### Scenario: Safe greeting is permitted
- **WHEN** a safe greeting is submitted under an `ALLOW_UNGROUNDED` policy
- **THEN** it follows the normal generation path and is labeled according to its provenance

#### Scenario: Greeting is not permitted without evidence
- **WHEN** a greeting is submitted under `REQUIRE_ALLOWED_SOURCE` or `REFUSE`
- **THEN** the service returns the configured safe outcome without a general answer
