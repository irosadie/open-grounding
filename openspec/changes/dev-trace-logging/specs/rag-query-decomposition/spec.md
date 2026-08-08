## ADDED Requirements

### Requirement: Query decomposition dev trace event
`QueryDecomposer.decompose()` SHALL emit a dev trace event after the LLM returns sub-queries.

#### Scenario: Decompose trace in active mode
- **WHEN** `RAG_DEV_TRACE` is active and decomposition is triggered
- **THEN** a trace event `"query.decompose"` is emitted with `count` (number of sub-queries), `sub_queries` (list of strings, verbose mode only), `system_tail` (last 300 chars of system prompt), `user_tail` (last 300 chars of user prompt), and `ms`

#### Scenario: sub_queries list omitted in summary mode
- **WHEN** mode is `"summary"`
- **THEN** `"query.decompose"` summary line contains `count=N` but does NOT include the full sub-query list

#### Scenario: sub_queries list present in verbose mode
- **WHEN** mode is `"verbose"`
- **THEN** `"query.decompose"` JSON line contains `"sub_queries": ["...", "..."]` with all sub-query strings
