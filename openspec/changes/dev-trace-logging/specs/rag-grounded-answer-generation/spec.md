## ADDED Requirements

### Requirement: Generation LLM context dev trace event
`RagGenerationService` SHALL emit a dev trace event after the prompt is assembled and before the LLM call, and a second event after the LLM responds.

#### Scenario: LLM context trace before generation
- **WHEN** `RAG_DEV_TRACE` is active and the generation prompt is assembled
- **THEN** a trace event `"query.llm_context"` is emitted with `system_tail` (last 300 chars of system prompt), `user_tail` (last 300 chars of user prompt), `history_turns` (number of conversation history messages prepended), and `ms`

#### Scenario: Generation result trace after LLM responds
- **WHEN** `RAG_DEV_TRACE` is active and the LLM returns a response
- **THEN** a trace event `"query.generation"` is emitted with `ms` (LLM call duration), `facts` (count of facts in response), `inferences` (count), `conflicts` (count), `limitations` (count)

#### Scenario: Verbose includes token estimate
- **WHEN** mode is `"verbose"`
- **THEN** `"query.llm_context"` JSON includes `"token_estimate"` — an integer approximation of total prompt tokens (chars / 4)

#### Scenario: Summary line is concise
- **WHEN** mode is `"summary"`
- **THEN** `"query.llm_context"` summary line contains `history_turns=N` and `"query.generation"` line contains `facts=N inferences=N ms=N`
