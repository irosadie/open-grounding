## ADDED Requirements

### Requirement: DevTracer utility singleton
The system SHALL provide a `DevTracer` class in `apps/api/app/core/dev_trace.py` as the single utility responsible for all dev trace emission. A module-level `get_tracer()` factory SHALL return a singleton instance. The tracer SHALL be a no-op when `RAG_DEV_TRACE` is unset or `"off"`.

#### Scenario: Tracer is disabled by default
- **WHEN** `RAG_DEV_TRACE` env var is not set or set to `"off"`
- **THEN** `get_tracer().enabled` returns `False` and no output is emitted for any trace call

#### Scenario: Tracer activates in summary mode
- **WHEN** `RAG_DEV_TRACE=summary`
- **THEN** `get_tracer().enabled` returns `True` and `get_tracer().mode` returns `"summary"`

#### Scenario: Tracer activates in verbose mode
- **WHEN** `RAG_DEV_TRACE=verbose`
- **THEN** `get_tracer().enabled` returns `True` and `get_tracer().mode` returns `"verbose"`

### Requirement: RAG_DEV_TRACE settings field
The `Settings` class SHALL include a field `RAG_DEV_TRACE: Literal["off", "summary", "verbose"]` defaulting to `"off"`. The `DevTracer` singleton SHALL be initialised from this settings value at app/worker startup.

#### Scenario: Settings default
- **WHEN** `RAG_DEV_TRACE` is absent from the environment
- **THEN** `settings.RAG_DEV_TRACE` equals `"off"`

#### Scenario: Settings accepts valid values
- **WHEN** `RAG_DEV_TRACE` is set to `"summary"` or `"verbose"`
- **THEN** `settings.RAG_DEV_TRACE` reflects that value without error

### Requirement: Per-operation timing context manager
The `DevTracer` SHALL expose an async context manager `tracer.op(event: str, **meta)` that measures wall-clock duration in milliseconds for the wrapped block and emits a trace event on exit.

#### Scenario: op() measures duration
- **WHEN** a code block is wrapped with `async with tracer.op("embed.batch", count=128)`
- **THEN** on exit the tracer emits an event with `"event": "embed.batch"`, `"count": 128`, and `"ms": <measured duration>`

#### Scenario: op() is a no-op when disabled
- **WHEN** tracer is disabled
- **THEN** `tracer.op()` context manager completes without any I/O or timing overhead

### Requirement: Summary mode output format
In `summary` mode the tracer SHALL emit a single human-readable line per event to stdout, prefixed with `[DEV]`, containing the event name and all meta key-value pairs.

#### Scenario: Summary line format
- **WHEN** mode is `"summary"` and event `"query.plan"` is emitted with `route="GROUNDED"` and `ms=45`
- **THEN** stdout receives a line like `[DEV] query.plan route=GROUNDED ms=45`

### Requirement: Verbose mode output format
In `verbose` mode the tracer SHALL emit a JSON object per event to stdout, one object per line (NDJSON), containing `"event"`, `"ts"` (ISO-8601 UTC), all meta fields, and `"ms"`.

#### Scenario: Verbose JSON line format
- **WHEN** mode is `"verbose"` and event `"query.llm_context"` is emitted
- **THEN** stdout receives a valid JSON line with at minimum `{"event": "query.llm_context", "ts": "...", "ms": ...}`

#### Scenario: Verbose includes all meta fields
- **WHEN** meta includes `chunks=8`, `tokens=3241`
- **THEN** the JSON line contains `"chunks": 8` and `"tokens": 3241`

### Requirement: LLM prompt preview truncation
When a trace event includes prompt content (system prompt or user prompt), the tracer SHALL include only the **last 300 characters** of each prompt string, keyed as `system_tail` and `user_tail` respectively. Full prompt text SHALL NOT be emitted in either mode.

#### Scenario: Prompt tail in verbose mode
- **WHEN** mode is `"verbose"` and a generation trace event is emitted with a 4000-char system prompt
- **THEN** `"system_tail"` in the JSON contains exactly the last 300 characters of the system prompt

#### Scenario: Prompt tail in summary mode
- **WHEN** mode is `"summary"` and a generation trace event is emitted
- **THEN** the summary line includes `system_tail=<last 300 chars>` truncated inline (max 300 chars shown)

### Requirement: No production overhead
All trace instrumentation code paths SHALL be guarded by `if not tracer.enabled: return` or equivalent before any string formatting, timing, or I/O work. When `RAG_DEV_TRACE` is `"off"`, zero additional CPU work SHALL occur per pipeline operation.

#### Scenario: Disabled tracer causes no overhead
- **WHEN** `RAG_DEV_TRACE` is `"off"` and the ingestion pipeline processes 1000 chunks
- **THEN** no trace-related string formatting or stdout writes occur
