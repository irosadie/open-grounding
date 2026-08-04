# rag-grounded-answer-generation Specification

## Purpose
TBD - created by archiving change rag-grounded-query. Update Purpose after archive.
## Requirements
### Requirement: Generation is evidence-bound and schema-validated
The system SHALL generate through a provider-neutral port using a versioned prompt that
limits factual knowledge claims to selected evidence, distinguishes inference from
source fact, reports insufficient/conflicting evidence, and ignores instructions inside
sources. Provider output MUST parse into an internal answer schema and MUST NOT include
hidden chain-of-thought.

#### Scenario: Evidence is insufficient for a factual claim
- **WHEN** selected evidence cannot support a requested material fact
- **THEN** the generated outcome states the limitation or abstains rather than inventing
  a citation or unsupported answer

### Requirement: Final answers pass bounded validation and repair
The system SHALL validate answer schema, citation ID validity, material-claim coverage,
contradictions, policy/PII output, and format before release. It MAY perform one
bounded repair; an invalid repaired result MUST abstain or fail safely.

#### Scenario: Generated answer includes an invalid citation
- **WHEN** validation finds a citation not present in the selected evidence context
- **THEN** the system performs at most one repair and otherwise does not release the
  unsupported factual claim

### Requirement: SSE emits only safe final answer content
The system SHALL support SSE events for start, route, retrieval summary, answer delta,
citations, completion, and failure. It MUST emit answer deltas only after the final
answer has passed required validation and MUST NOT emit secrets, raw vectors, hidden
prompts, hidden reasoning, or cross-tenant metadata.

#### Scenario: Validated answer streams to a client
- **WHEN** a query requests streaming and answer validation succeeds
- **THEN** the client receives ordered SSE events ending in final citations,
  limitations, evidence level, and trace identity

