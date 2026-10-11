## ADDED Requirements

### Requirement: Administrators can manage effective answer behavior and guardrails

The console SHALL provide authorized administrators with settings for answer behavior and
guardrails, including persona, response style, output token budget, source policy,
greeting policy, no-evidence action, and guardrail profile. The UI MUST validate bounds,
show the active version, and make immutable platform rules visibly read-only.

#### Scenario: Administrator saves a valid policy
- **WHEN** an authorized administrator submits valid answer behavior and guardrail settings
- **THEN** the console persists an active version and shows the effective configuration summary

#### Scenario: User lacks permission to edit policy
- **WHEN** a non-admin opens the settings surface
- **THEN** the console shows the effective policy as read-only and offers no write control

### Requirement: Query results expose honest provenance and policy outcomes

The retrieval UI SHALL distinguish document-grounded, MCP-supported, general/non-grounded,
abstained, refused, and operational-failure outcomes. It MUST NOT label general or
unvalidated MCP content as document-grounded and MUST show safe limitations when policy
prevents an answer.

#### Scenario: Answer is supported by MCP
- **WHEN** the API returns validated MCP provenance
- **THEN** the UI displays the safe tool/source reference and does not present it as a document citation

#### Scenario: Strict policy prevents an answer
- **WHEN** the API returns an abstain or refusal because required evidence is unavailable
- **THEN** the UI shows the policy-safe limitation and renders no rejected answer content

### Requirement: Streaming and non-streaming views share policy semantics

The UI SHALL render the same effective route, provenance, guardrail outcome, limitations,
and citations for streaming and non-streaming responses. It MUST not display answer deltas
until the API has marked the answer as validated.

#### Scenario: Stream completes with a policy label
- **WHEN** a validated stream emits completion metadata with route and provenance
- **THEN** the UI renders the answer with the same policy label and evidence details as the blocking response
