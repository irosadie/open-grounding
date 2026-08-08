## ADDED Requirements

### Requirement: Ingestion stage dev trace events
Each ingestion pipeline stage worker (parse, chunk, embed, index, validate) SHALL emit dev trace events per operation when the tracer is active. Each operation SHALL be wrapped with `tracer.op()` to capture duration.

#### Scenario: Parse stage trace
- **WHEN** `RAG_DEV_TRACE` is active and the parse stage processes a document version
- **THEN** a trace event `"ingestion.parse"` is emitted with `version_id`, `chars` (extracted character count), and `ms`

#### Scenario: Chunk stage trace
- **WHEN** `RAG_DEV_TRACE` is active and the chunk stage processes a document version
- **THEN** a trace event `"ingestion.chunk"` is emitted with `version_id`, `chunks` (number of chunks produced), `strategy`, `chunk_size`, and `ms`

#### Scenario: Embed stage trace
- **WHEN** `RAG_DEV_TRACE` is active and the embed stage processes chunks
- **THEN** a trace event `"ingestion.embed"` is emitted with `version_id`, `vectors` (count), `dim` (embedding dimension), and `ms`

#### Scenario: Index stage trace
- **WHEN** `RAG_DEV_TRACE` is active and the index stage upserts vectors
- **THEN** a trace event `"ingestion.index"` is emitted with `version_id`, `upserted` (count), `collection`, and `ms`

#### Scenario: Validate stage trace
- **WHEN** `RAG_DEV_TRACE` is active and the validate stage finalizes a document
- **THEN** a trace event `"ingestion.validate"` is emitted with `version_id`, `final_state` (`READY` or `FAILED`), `vectors`, and `ms`

#### Scenario: Tracer disabled — no stage trace emitted
- **WHEN** `RAG_DEV_TRACE` is `"off"`
- **THEN** no trace events are emitted from any ingestion stage worker
