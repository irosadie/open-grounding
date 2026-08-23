## ADDED Requirements

### Requirement: Document intake uses the presigned upload flow

The ingestion workbench SHALL create an intake request via `/rag/ingestion/intake`, upload the
file to the returned target, and complete intake via `/rag/ingestion/complete` with the content
checksum. It MUST validate file type and size client-side before requesting an intake and MUST
NOT buffer the source file in application memory.

#### Scenario: User uploads a supported document

- **WHEN** an authenticated user selects a supported file (PDF, Markdown, or plain text) within
  the configured size limit and a knowledge base
- **THEN** the UI creates an intake, uploads to the presigned target, completes intake with the
  checksum, and shows the document version as enqueued for ingestion

#### Scenario: User selects an unsupported file

- **WHEN** a user selects a file whose MIME type or extension is unsupported or whose size
  exceeds the limit
- **THEN** the UI rejects the file before requesting an intake and explains why without
  contacting the backend

### Requirement: Ingestion status surfaces worker pipeline stages to completion

The ingestion workbench SHALL poll `/rag/ingestion/status/{document_version_id}` while a
version is in a non-terminal state and render the lifecycle state, current stage, attempts, and
quality outcome as a visible pipeline (parse → embed → index → ready/failed). Polling MUST stop
on a terminal state or component unmount and MUST use a bounded interval.

#### Scenario: Ingestion progresses through the worker pipeline

- **WHEN** an enqueued document version transitions through parse, embed, and index stages
- **THEN** the UI shows the current stage and progress and stops polling once the version
  reaches a terminal ready or failed state

#### Scenario: A stage fails and is recoverable

- **WHEN** the status endpoint reports a recoverable failed stage with attempts recorded
- **THEN** the UI shows the failure classification and offers the bounded retry action the
  backend exposes without mutating the prior generation in place

### Requirement: The document list is tenant-scoped and paginated

The ingestion workbench SHALL list document versions scoped to the server-derived tenant and
selected knowledge base using the existing success envelope. It MUST NOT display another
tenant's documents and MUST paginate or virtualize long lists to keep the view responsive.

#### Scenario: User lists documents in a knowledge base

- **WHEN** an authenticated user opens the workbench with a knowledge base selected
- **THEN** the UI lists only the document versions the caller is authorized to see for that
  tenant and knowledge base with their lifecycle state and current stage

### Requirement: Deletion is soft and confirmed

The ingestion workbench SHALL soft-delete a document version via
`DELETE /rag/ingestion/{document_version_id}` only after an explicit confirmation. It MUST show
the resulting scheduled-for-deletion state and MUST NOT delete without confirmation or expose a
hard-purge control.

#### Scenario: User deletes a document version

- **WHEN** a user confirms deletion of a document version
- **THEN** the UI calls the soft-delete endpoint, the version is removed from active retrieval
  in the list, and the deletion lifecycle is auditable through the status surface