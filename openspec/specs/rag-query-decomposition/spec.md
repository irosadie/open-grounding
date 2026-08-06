# rag-query-decomposition Specification

## Purpose
TBD - created by archiving change rag-query-deferred-followups. Update Purpose after archive.
## Requirements
### Requirement: Multi-hop decomposition is opt-in and evaluation-gated
The system SHALL perform LLM-driven multi-query, HyDE, step-back, or multi-hop planning
only as opt-in behavior gated by an evaluation set proving that decomposition improves
retrieval recall without degrading groundedness or abstention quality. It MUST bound
decomposition depth and MUST NOT make it default behavior until the evaluation gate is
met and reviewed.

#### Scenario: Decomposition would exceed the bounded depth
- **WHEN** a multi-hop plan exceeds the configured maximum decomposition depth
- **THEN** the system truncates the plan to the bound and proceeds with the permitted
  sub-queries only, recording the truncation in the trace
