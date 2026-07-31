## Why

Ingested documents are useful only when users can receive answers that are secure,
grounded in permitted evidence, cite their sources, and decline to guess when evidence
is insufficient. A direct model call or raw vector similarity is not enough: it can
ignore ACLs, overfit to one source, and produce unsupported claims.

## What Changes

- Add tenant- and ACL-scoped RAG query requests with input guardrails, bounded
  conversation context, query normalization, and deterministic route selection.
- Add default hybrid Qdrant retrieval using dense and sparse representations, server-
  side mandatory filters, RRF fusion, deduplication/diversity selection, and
  cross-encoder reranking.
- Add calibrated-evidence confidence decisions that generate, retry once, clarify, or
  abstain without treating a raw vector score as confidence.
- Add context construction with parent expansion, token budgets, untrusted-source
  isolation, stable citations, and repeat ACL checks.
- Add grounded answer generation, citation/claim validation, policy validation, one
  bounded repair, and SSE response events with final trace metadata.
- Add answer runs, retrieval traces, citations, feedback hooks, evaluation fixtures,
  and operational measurements without storing hidden chain-of-thought.
- Exclude graph retrieval, live tool execution, automatic multi-hop decomposition,
  long-term memory, autonomous agents, and numeric confidence scores before a labeled
  calibration dataset exists.

## Capabilities

### New Capabilities

- `rag-query-security-and-planning`: Authorize, guard, normalize, and route a query
  within tenant, knowledge-base, ACL, policy, and bounded-budget constraints.
- `rag-hybrid-retrieval-and-ranking`: Retrieve eligible evidence through dense/sparse
  Qdrant search, RRF, deduplication/diversity, and reranking.
- `rag-evidence-context-and-citations`: Build token-bounded, citation-stable,
  ACL-rechecked evidence context from active document generations.
- `rag-grounded-answer-generation`: Generate, validate, repair, stream, or abstain
  from answers using evidence-bound provider contracts.
- `rag-answer-evaluation-and-operations`: Persist safe answer traces, feedback,
  evaluation fixtures, and bounded metrics for quality and recovery.

### Modified Capabilities

None. No main OpenSpec capability specifications exist yet.

## Impact

- Adds FastAPI query/SSE endpoints, Pydantic contracts, application use cases,
  repositories, provider ports/adapters, Alembic migrations, tests, and generated
  OpenAPI operations.
- Consumes the tenant, platform, and ingestion changes: it requires active validated
  document generations, Qdrant payload indexes, object-store artifacts, model/index
  profiles, and tenant-aware authorization.
- Adds local or hosted provider configuration for query embedding, sparse encoding,
  reranking, and generation without coupling domain code to one vendor.
- Adds no new mandatory Docker service and does not add a frontend chat UI in this
  change; clients can consume the HTTP and SSE contracts first.
