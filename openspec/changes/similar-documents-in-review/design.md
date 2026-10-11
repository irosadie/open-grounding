## Context

The review page already loads parsed text through the ingestion API, while the query
pipeline already knows how to embed a bounded text query and apply the server-derived
Qdrant policy filter. Active index generations are tied to document versions and can be
joined back to catalog documents for titles and lifecycle state. See proposal.md and the
delta specs for the externally visible contract.

## Goals / Non-Goals

**Goals:**

- Reuse the existing retrieval policy and active index rather than introducing a second
  similarity implementation.
- Keep the endpoint read-only and bounded in work, result count, preview size, and query
  text sent to the embedding provider.
- Make the review page useful when there are no indexed documents or when retrieval is
  temporarily unavailable.

**Non-Goals:**

- Similarity search across tenants or across knowledge bases.
- Indexing the document before approval, storing similarity history, or adding database
  tables/migrations.
- Replacing the existing query-time hybrid retrieval or changing answer ranking.

## Decisions

### Dedicated review endpoint

Add a `GET /rag/ingestion/{version_id}/similar-documents` endpoint instead of expanding
the parsed-text response. This keeps the existing review load fast and lets the UI handle
similarity retrieval as an independent, recoverable panel.

### Dense semantic retrieval with normal policy filters

Use the active index profile's dense embedding model and existing `search_permitted`
path, scoped to the source document's knowledge base and active generation IDs. Sparse
fusion is intentionally not required for this review aid: dense similarity is stable for
long parsed documents and avoids making a second sparse-provider failure block the panel.

### Group chunks into document results

Qdrant returns chunk-level matches, so results are grouped by document version and keep
the highest-scoring chunk as the document score and preview. Catalog rows provide titles,
document IDs, and lifecycle state. The current version is explicitly excluded even if a
stale generation ever contains its points.

### Independent frontend query

The console uses a React Query hook keyed by version ID and renders a separate card below
parsed content. Errors are local to that card; editing and lifecycle actions continue to
use the existing hooks.

## Risks / Trade-offs

- [Long parsed text can exceed embedding-provider limits] → truncate the similarity
  embedding input to a bounded prefix while preserving the full source only in the
  catalog/editor.
- [A KB may contain many active generations] → retrieve a bounded candidate set, group
  and cap document results, and use the same active-generation policy as normal queries.
- [Qdrant/provider outage during review] → return a recoverable API error and keep the
  panel non-blocking; approval and parsed-text actions do not depend on the result.
- [Chunk scores are not calibrated confidence] → label the value as similarity and do
  not reuse the answer confidence/evidence level contract.

## Migration Plan

No database migration or backfill is required. Deploy the API and frontend together; old
clients ignore the new endpoint. Rollback is code-only by removing the endpoint/hook/card,
with no persisted data to clean up.
