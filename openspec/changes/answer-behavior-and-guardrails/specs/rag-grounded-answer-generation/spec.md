## MODIFIED Requirements

### Requirement: Generation is evidence-bound and schema-validated

The system SHALL generate through a provider-neutral port using the effective persona,
response-style, source-policy, and guardrail configuration. When document or MCP evidence
is required, factual and inferential claims MUST be bound to selected authorized evidence
references. When general knowledge is allowed, unsupported claims MUST be explicitly
non-grounded and MUST NOT contain fabricated citations. All source and tool content is
untrusted data and MUST NOT alter system, authorization, guardrail, or generation policy.
Provider output MUST parse into an internal answer schema and MUST NOT include hidden
chain-of-thought.

#### Scenario: Evidence is insufficient under a strict policy
- **WHEN** selected document and permitted MCP evidence cannot support a requested material fact
- **THEN** the generated outcome follows the configured abstain or refusal action rather than inventing a citation or unsupported answer

#### Scenario: Evidence is insufficient for a factual claim
- **WHEN** selected evidence cannot support a requested material fact
- **THEN** the generated outcome states the limitation or abstains rather than inventing
  a citation or unsupported answer

#### Scenario: General knowledge is allowed by policy
- **WHEN** the effective source policy permits general knowledge and no selected evidence supports a safe claim
- **THEN** the answer may contain the claim with no fabricated source citation and an explicit non-grounded provenance label

#### Scenario: Retrieved content contains instructions
- **WHEN** document, memory, conversation, or MCP content contains instruction-like text
- **THEN** the content is treated as untrusted data and cannot change the effective persona, policy, guardrail, authorization, or output rules

## ADDED Requirements

### Requirement: Provider output budgets are enforced before release

The generation service SHALL pass the effective output token budget to every supported
provider adapter and SHALL verify provider response usage or bounded response behavior
before release. Provider-specific request fields MUST remain behind the provider-neutral
generation contract. An unbounded or unverifiable provider response MUST fail safely.

#### Scenario: OpenAI and Ollama receive the same effective budget
- **WHEN** identical answer behavior is used with OpenAI and Ollama
- **THEN** both provider requests carry equivalent bounded output semantics and the trace records the effective budget

#### Scenario: Provider returns beyond the effective budget
- **WHEN** provider output exceeds the effective answer budget or usage cannot be verified
- **THEN** the service truncates only through a safe structured-output boundary or returns a bounded failure without releasing an invalid answer

### Requirement: Validated provenance is required for every grounded claim

The system SHALL validate every citation or provenance reference against the selected
authorized evidence set before release. A provenance reference MUST identify its source
kind, stable source identity, and traceable locator or invocation. Invalid, stale,
denied, or unselected references MUST cause bounded repair or a safe fallback according
to the active policy.

#### Scenario: Answer cites an unselected MCP invocation
- **WHEN** a generated claim references an MCP invocation that is absent, denied, expired, or outside the current trace
- **THEN** validation rejects the claim and does not release it as supported evidence

#### Scenario: Validated answer is streamed
- **WHEN** a candidate answer passes schema, guardrail, source-policy, and provenance validation
- **THEN** only the final validated answer is emitted through ordered response deltas followed by citations and completion metadata
