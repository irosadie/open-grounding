## Why

Document review currently shows only the parsed text, so an operator cannot quickly
check whether the incoming document is already represented by another document in the
same knowledge base. A tenant-scoped semantic comparison during review will make
duplicates and closely related sources visible before approval and indexing.

## What Changes

- Add a review-time API that finds the most similar indexed document versions in the
  current document's knowledge base.
- Reuse the existing tenant, ACL, classification, active-generation, and embedding
  policy when searching for similar documents.
- Exclude the document being reviewed and return bounded results with title, preview,
  lifecycle state, source identifiers, and a similarity score.
- Add a "Similar documents" panel to the document review screen with loading, empty,
  error, score, and navigation states.
- Keep the feature read-only; it does not create database tables, vectors, or new
  indexing generations.

## Capabilities

### New Capabilities

- `rag-document-similarity`: Tenant-scoped semantic similarity lookup for a document
  version during review.

### Modified Capabilities

- `rag-source-intake-and-versioning`: Document review exposes related indexed versions
  from the same knowledge base without changing ingestion lifecycle behavior.
- `rag-ingestion-workbench-ui`: The review workbench shows related documents and links
  to their authorized document views.

## Impact

- Backend: new application service, tenant-scoped retrieval endpoint, and response
  contract; it uses the existing active index profile, embedding adapter, Qdrant
  policy filter, and catalog repositories.
- Frontend: shared response type, API route/query key, React Query hook, and review
  panel.
- Tests: backend service/route coverage and frontend type/build checks.
- Persistence: no schema or migration changes; no similarity results are retained.
