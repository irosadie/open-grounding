## ADDED Requirements

### Requirement: Query plan dev trace event
The `plan_query` call in `RagQueryService` SHALL emit a dev trace event after the plan is resolved.

#### Scenario: Plan trace in active mode
- **WHEN** `RAG_DEV_TRACE` is active and `plan_query()` returns a `QueryPlan`
- **THEN** a trace event `"query.plan"` is emitted with `route` (`GROUNDED` or `ABSTAIN`), `standalone` (the resolved standalone query string), and `ms`

#### Scenario: Abstain route traced
- **WHEN** `plan_query()` returns route `ABSTAIN`
- **THEN** `"query.plan"` event is still emitted with `route=ABSTAIN`

### Requirement: Evidence context dev trace event
After `build_evidence_context()` assembles chunks into the evidence prompt, a dev trace event SHALL be emitted.

#### Scenario: Evidence trace in active mode
- **WHEN** `RAG_DEV_TRACE` is active and evidence context is built
- **THEN** a trace event `"query.evidence"` is emitted with `chunks` (number of chunks included), `tokens` (estimated token count of evidence context), `budget` (configured `rag_context_token_budget`), and `ms`

#### Scenario: Evidence trace in verbose mode includes gate result
- **WHEN** mode is `"verbose"` and evidence gating runs
- **THEN** `"query.evidence"` event additionally includes `gated` (bool — whether evidence passed the gate)
