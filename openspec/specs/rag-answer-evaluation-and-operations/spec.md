# rag-answer-evaluation-and-operations Specification

## Purpose
TBD - created by archiving change rag-grounded-query. Update Purpose after archive.
## Requirements
### Requirement: Answer runs are reproducible and retention-aware
The system SHALL persist tenant-scoped answer-run metadata including request/trace ID,
query forms, profile/config snapshots, retrieval summary, selected evidence identities,
citations, validation outcome, latency, usage, and limitations. It MUST NOT persist
hidden chain-of-thought, provider secrets, or unnecessary raw source duplication.

#### Scenario: Operator investigates an answer
- **WHEN** an authorized operator inspects an answer run within retention policy
- **THEN** the trace identifies the evidence and configuration used without exposing
  hidden reasoning or another tenant's records

### Requirement: Feedback and evaluation measure grounded quality
The system SHALL support tenant-scoped answer feedback and fixture-based evaluation for
retrieval recall, citation correctness/coverage, groundedness, abstention quality,
latency, and failure rate. Advanced retrieval weighting or numeric confidence MUST NOT
become default without recorded evaluation improvement.

#### Scenario: Candidate retrieval profile is evaluated
- **WHEN** an operator evaluates a changed retrieval or reranker profile against the
  labeled fixture set
- **THEN** the system records quality and latency results before that profile can be
  promoted as default

### Requirement: Query operations are observable and bounded
The system SHALL emit bounded tenant-aware metrics and audit events for admission,
retrieval, reranking, confidence outcomes, generation, validation, abstention, SSE
completion, and failures. It MUST apply configured timeout, concurrency, and retention
limits to every query stage.

#### Scenario: Generation provider fails
- **WHEN** the generation provider fails or exceeds its configured timeout
- **THEN** the system records a tenant/trace-correlated failure and returns a safe
  failure or abstention without leaking provider details

