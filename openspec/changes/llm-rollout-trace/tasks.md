## 1. Configuration and trace foundation

- [x] 1.1 Add `rag_llm_trace_enabled: bool = False` and `rag_llm_trace_dir` settings, verify `RAG_LLM_TRACE_ENABLED=true|false` parses correctly and the default is disabled
- [x] 1.2 Create the stable JSONL event envelope and event-name constants, verify each emitted line contains `schema_version`, `seq`, `ts`, `trace_id`, `event`, and `payload`
- [x] 1.3 Implement the context-local recorder with no-op disabled behavior, per-trace file creation, ordered sequence numbers, and best-effort append errors; verify disabled mode performs no filesystem writes
- [x] 1.4 Implement recursive redaction for credentials, authorization headers, cookies, secret fields, and credential-bearing URLs; verify prompt/content remains available while secrets are masked
- [x] 1.5 Add the default `.runtime/llm-traces/` directory to `.gitignore` and document local trace handling

## 2. Trace lifecycle and LLM boundaries

- [x] 2.1 Start/close rollout contexts at HTTP query and background worker entry points, verify every enabled flow produces `session_meta`, lifecycle, and completion/failure events
- [x] 2.2 Instrument the grounded generation provider boundary to record the exact request body, model parameters, provider response, usage, request ID, retry, and error; verify a test can inspect the complete ordered messages
- [x] 2.3 Instrument query decomposition and query planning provider calls, including available tools, rendered prompts, raw outputs, fallback, timeout, and parse-error paths; verify fallback traces remain complete
- [x] 2.4 Instrument memory summarization, calibration, and every remaining direct provider call discovered by repository-wide search; verify no current chat/generation call site bypasses the recorder
- [x] 2.5 Record stream chunks when a provider path streams and record context assembly/compaction boundaries when they occur; verify chunk ordering and final response correlation. Current provider adapters use `stream=false`; the stream event is reserved for future streaming paths while context/compaction events are active.

## 3. Tool and agent-loop coverage

- [x] 3.1 Record tool catalog/schema supplied to the planner or LLM, including tool identity and safe metadata; verify the event is emitted before the planning request
- [x] 3.2 Instrument `TaskExecutor` and `McpRuntimeService` for requested, started, permitted/denied, invalid-argument, completed, timeout, and failed tool events; verify existing authorization and timeout outcomes are unchanged
- [x] 3.3 Record full bounded tool arguments/results and follow-up LLM request correlation with `trace_id`, `turn_id`, `seq`, and parent event metadata; verify concurrent tasks remain isolated to the correct rollout file
- [x] 3.4 Record retry, safe abstention, final answer, and uncaught error events at the query lifecycle boundary; verify trace write failures never fail the user request

## 4. Verification

- [x] 4.1 Add unit tests for boolean settings, disabled no-op behavior, JSONL validity, monotonic sequence numbers, per-trace isolation, and redaction; verify the focused test suite passes
- [x] 4.2 Add integration tests for a full query with planner/decomposer/generation plus a successful MCP tool; verify the JSONL event order exposes every LLM and tool step
- [x] 4.3 Add integration tests for denied, invalid, timeout, retry, and provider-error paths; verify diagnostic events are present and business responses remain unchanged
- [x] 4.4 Run a manual smoke test with `RAG_LLM_TRACE_ENABLED=true`, inspect a generated rollout with `jq`, then repeat with `false` and verify no new rollout file is created
- [x] 4.5 Run the relevant API tests, lint/type checks, and repository validation; verify the existing `RAG_DEV_TRACE` off/summary/verbose behavior remains compatible
