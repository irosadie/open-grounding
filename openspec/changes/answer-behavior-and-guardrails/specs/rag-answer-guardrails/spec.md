## Purpose

Defines independent, staged guardrail profiles that protect query input, tool use, and
released output without relying on model compliance or persona instructions.

## ADDED Requirements

### Requirement: Guardrails are independent, layered, and versioned

The system SHALL provide a versioned guardrail profile separate from persona, source
policy, planner configuration, and MCP permissions. Guardrails SHALL be evaluated at
input, tool, and output boundaries. An immutable platform baseline MUST remain active;
tenant or knowledge-base profiles MAY add restrictions but MUST NOT weaken the baseline.
Every decision SHALL include the effective profile version and evaluation stage.

#### Scenario: Knowledge-base profile adds a restriction
- **WHEN** a knowledge base has a stricter guardrail profile than the deployment baseline
- **THEN** the stricter profile applies to its queries and the effective version is recorded

#### Scenario: Configuration attempts to disable the baseline
- **WHEN** an administrator submits a profile that disables a platform baseline rule
- **THEN** validation rejects the weakening change and preserves the active profile

### Requirement: Input guardrails run before retrieval, generation, and memory side effects

The system SHALL evaluate query text, request metadata, and relevant conversation input
before retrieval, generation, MCP planning, or memory scheduling. A blocked request MUST
not invoke an LLM, retrieve evidence, invoke an MCP tool, or enqueue memory work. The
response MUST expose only a safe refusal code and user-safe message, never protected
policy details.

#### Scenario: Prompt-extraction request is blocked
- **WHEN** input guardrails detect a protected prompt, credential, or secret-extraction request
- **THEN** the service returns a refusal outcome before generation and records a redacted decision

#### Scenario: Input guardrail evaluation fails
- **WHEN** the guardrail evaluator times out or fails closed
- **THEN** the service refuses or safely fails the request without continuing the pipeline

### Requirement: Tool guardrails protect every MCP invocation

Before an MCP call, the system SHALL verify the effective source policy, server and tool
permission, argument schema, per-query call budget, timeout, payload budget, and any
required confirmation or risk rule. A denied, invalid, timed-out, or failed call MUST
not become answer evidence.

#### Scenario: Tool is not permitted by policy
- **WHEN** a planner selects an MCP tool that is not allowed by the effective profile
- **THEN** the tool is not invoked, the task is recorded as denied or skipped, and no tool evidence is exposed as valid support

#### Scenario: MCP call exceeds the query tool budget
- **WHEN** an execution would exceed the configured maximum number of MCP calls or payload budget
- **THEN** the call is denied and the answer pipeline follows the configured safe fallback

### Requirement: Output guardrails run before answer release

The system SHALL evaluate the complete candidate answer, citations, provenance references,
policy labels, and limitations after generation and before any non-empty answer delta,
blocking response, async result, or persisted assistant answer is released. A blocked or
invalid result MUST release no rejected answer content and MUST return a safe refusal or
operational failure outcome.

#### Scenario: Generated answer contains protected content
- **WHEN** output guardrails detect secrets, hidden prompts, disallowed policy content, or unsafe output
- **THEN** the service suppresses the answer content, returns a safe refusal, and records the guardrail decision

#### Scenario: Output guardrail detects an unsupported claim
- **WHEN** a candidate claim violates the active source policy or lacks valid provenance
- **THEN** the candidate is rejected or repaired within the bounded validation policy and no unvalidated delta is emitted

### Requirement: Guardrail decisions are auditable without sensitive duplication

The system SHALL persist or emit tenant-scoped guardrail decisions with trace ID, stage,
profile version, decision, stable reason code, duration, and outcome. It MUST NOT persist
raw credentials, hidden prompts, hidden reasoning, unbounded user content, or raw tool
arguments solely for guardrail auditing.

#### Scenario: Operator investigates a refused query
- **WHEN** an authorized operator opens a retained trace for a refused query
- **THEN** the trace shows the stage, profile version, and safe reason code without exposing protected input or policy internals
