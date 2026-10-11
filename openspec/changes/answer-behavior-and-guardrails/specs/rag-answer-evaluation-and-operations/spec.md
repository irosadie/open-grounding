## MODIFIED Requirements

### Requirement: Answer runs are reproducible and retention-aware

The system SHALL persist tenant-scoped answer-run metadata including request/trace ID,
query forms, effective answer-behavior and guardrail profile versions, retrieval and
MCP provenance summaries, selected evidence identities, citations, validation outcome,
latency, bounded token usage, route, and limitations. It MUST NOT persist hidden
chain-of-thought, provider secrets, raw credentials, raw tool arguments, or unnecessary
raw source duplication.

#### Scenario: Operator investigates an answer
- **WHEN** an authorized operator inspects a retained answer run
- **THEN** the trace identifies the effective policies, evidence, provenance, and validation outcome without exposing hidden reasoning, secrets, or another tenant's records

#### Scenario: Policy version is retired after an answer
- **WHEN** an operator inspects an answer created under a retired policy version
- **THEN** the trace remains interpretable using the recorded immutable configuration snapshot and version metadata

## ADDED Requirements

### Requirement: Policy and guardrail outcomes are observable and evaluation-ready

The system SHALL emit tenant- and trace-correlated metrics and audit events for effective
policy selection, guardrail decisions by stage, source-policy route, MCP evidence use,
token-budget enforcement, validation, abstention, refusal, streaming completion, and
provider failure. Evaluation fixtures MUST cover every source policy, greeting policy,
guardrail stage, and provider budget path before a policy becomes the deployment default.

#### Scenario: Guardrail blocks a tool call
- **WHEN** a tool guardrail denies an MCP invocation
- **THEN** the trace and metrics record the stable stage and reason code, and the event contains no raw arguments or credential material

#### Scenario: New policy is promoted
- **WHEN** an operator attempts to make a new answer or guardrail policy the default
- **THEN** promotion requires passing policy-matrix evaluations for groundedness, provenance correctness, refusal behavior, latency, and failure rate

### Requirement: Configuration changes are auditable and reversible

Every create, update, activate, retire, and rollback action for answer behavior or
guardrail profiles SHALL record actor, tenant, previous version, new version, change
reason, and timestamp. Rollback MUST restore a previously validated version without
deleting its audit history.

#### Scenario: Operator rolls back a policy
- **WHEN** an authorized operator rolls back to a previous validated version
- **THEN** new queries use the restored version and the rollback action is visible in the audit trail
