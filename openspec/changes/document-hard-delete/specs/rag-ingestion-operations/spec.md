## ADDED Requirements

### Requirement: soft_delete enqueues ingestion.delete BullMQ job
After transitioning a document version lifecycle state to `DELETING`, `IngestionIntakeService.soft_delete` SHALL enqueue a job to the `ingestion.delete` BullMQ queue with `documentVersionId` and `tenantId` as payload.

#### Scenario: Delete job enqueued after soft_delete
- **WHEN** `DELETE /rag/ingestion/{document_version_id}` is called
- **THEN** the version lifecycle state transitions to `DELETING` and a job is added to `ingestion.delete` queue within the same request

#### Scenario: ingestion.delete worker registered
- **WHEN** the unified worker starts
- **THEN** a `bullmq.Worker` listening on `ingestion.delete` is active with concurrency 2 and the standard retry options
