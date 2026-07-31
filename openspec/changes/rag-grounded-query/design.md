## Context

The preceding tenant, platform, and ingestion changes provide authenticated tenant
context, active document/index generations, Qdrant dense/sparse payloads, canonical
chunks, parser quality, provider ports, and operational traces. This change turns that
corpus into answers with evidence instead of exposing raw search results or calling an
LLM without retrieval controls.

The first query release deliberately supports the default evidence path only. It uses
recent conversation context, deterministic query normalization, server-built filters,
parallel dense/sparse Qdrant retrieval, RRF, deduplication/diversity, cross-encoder
reranking, context/citation construction, evidence-bound generation, validation, and
SSE. Graph traversal, live tools, automatic decomposition, long-term memory, and
numeric confidence calibration are later changes.

## Goals / Non-Goals

**Goals:**

- Prevent tenant, ACL, classification, active-version, and time-policy bypass at every
  retrieval and source-expansion boundary.
- Produce grounded answers with stable citations or explicitly ask for clarification
  or abstain when permitted evidence is insufficient.
- Use hybrid dense/sparse retrieval safely despite incomparable score scales.
- Keep query and generation budgets bounded, observable, reproducible, and tunable by
  versioned profiles.
- Stream only validated final answer content and final trace/citation metadata.

**Non-Goals:**

- Graph, tool, web, database, or live transactional retrieval.
- Automatic multi-hop decomposition, multi-query, HyDE, step-back, or LLM planning as
  default behavior.
- Long-term memory, user preference storage, autonomous agents, or background action.
- A numeric confidence score until labeled evaluation data calibrates one.
- Frontend chat UI; HTTP and SSE contracts are the initial client integration.

## Decisions

### Query context and authorization are server-derived

The query request contains `conversationId`, `message`, allowed knowledge-base IDs,
optional safe metadata filters, mode, and stream preference. It never contains tenant
ID, ACL principals, clearance, active generation, or vector filter expressions. FastAPI
authenticates the actor, resolves immutable tenant context, verifies knowledge-base
access, applies rate/token/concurrency limits, then builds the filter server-side.

Every dense, sparse, parent expansion, canonical source fetch, and later retrieval
adapter receives the same predicate: tenant, authorized knowledge bases, active
generation/version, classification clearance, ACL principals, effective time range,
and allowed caller filters. Post-filtering is prohibited as a security boundary.

Recent conversation messages can inform standalone-query construction, but retrieved
content is never written into long-term memory. Original and normalized/standalone
queries are stored as trace fields rather than silently replacing user intent.

### Planning is deterministic and bounded in v1

The query analyzer uses deterministic policy/rules to route `grounded`, `clarify`, or
`abstain`. It identifies empty/oversize requests, policy violations, unavailable
knowledge bases, and low-evidence outcomes. V1 normalizes language/whitespace and may
make one standalone query; original query is always retrieved too. It does not call an
LLM planner or tool.

The configuration profile controls candidate counts, timeouts, input/output budgets,
and one optional retrieval rewrite attempt. Failure never creates an unbounded planner,
retrieval, generation, or repair loop.

### Hybrid Qdrant retrieval uses equal mandatory filters and RRF

The retriever creates dense and sparse representations with active compatible profiles
and prefetches them in parallel under the identical server-built Qdrant filter. RRF is
the default fusion algorithm because dense and sparse scores have different scales.
Any weighting, recency boost, or profile-specific fusion is disabled until evaluation
shows improvement.

Initial profile defaults are 50 dense candidates, 50 sparse candidates, 40 fused, 24
deduplicated/diverse candidates, 24 reranker candidates, and 6–12 selected context
chunks. These are configuration values, not embedded constants. Deduplication removes
same chunk/checksum/superseded content; MMR or a diversity heuristic prevents one
document/section from dominating without selecting irrelevant sources.

### Reranking and evidence confidence are separate decisions

A cross-encoder reranker scores query-plus-chunk candidates with bounded batching,
truncation, timeout, model/version tracing, and a deterministic fallback. It does not
override policy filters. The confidence gate uses evidence features such as reranker
score/margin, dense/sparse agreement, independent-source count, extraction quality,
freshness, and candidate coverage—not a single raw vector score.

Before a labeled calibration dataset exists, the gate returns explainable levels
(`high`, `medium`, `low`, `none`) and no numeric percentage. High proceeds; medium
may use one bounded retrieval rewrite; low/none clarifies or abstains. A future change
may expose numeric confidence only with calibration version and monitoring.

### Context is evidence-first and citation-stable

The context builder re-fetches selected canonical chunks, re-applies ACL/policy,
expands parent/neighbor content only within the same permitted document generation,
removes duplicates, and honors context/output token reserves. It marks source content
as untrusted data and isolates instruction-like text so documents cannot override the
system/policy prompt.

Each selected evidence item gets a stable citation ID such as `S1`, plus document,
version, title, page/section locator, and bounded supporting snippet. Citation IDs
remain tied to the chosen evidence throughout generation, validation, storage, and
SSE completion.

### Generation is schema-bound, validated, then streamed

The generation port receives only a versioned evidence-bound prompt. It must
distinguish supported fact from inference, cite every material factual claim, surface
conflicts/limitations, ignore instructions in source text, and never return hidden
chain-of-thought. Provider output is parsed into an internal answer schema.

V1 performs schema, citation-ID, citation-coverage, contradiction, policy/PII, and
format validation before the answer is released as final SSE deltas. It permits one
bounded repair using explicit validation feedback; failure produces an abstention or
safe failure event, not unsupported text. This raises time-to-first-token but avoids
streaming claims that must later be withdrawn.

SSE events are `response.started`, `response.route`, `response.retrieval_summary`,
`response.delta`, `response.citations`, `response.completed`, and `response.failed`.
No event exposes raw vectors, secrets, hidden prompts, hidden reasoning, or another
tenant's metadata.

### Answer traces enable evaluation without retaining hidden reasoning

`answer_runs`, retrieval candidates/summaries, selected context IDs, citations,
profile/config snapshots, latency/usage, validation outcome, feedback, and trace IDs
are persisted under tenant retention policy. Raw source text and chain-of-thought are
not copied into the trace. Evaluation fixtures measure retrieval recall, citation
correctness/coverage, groundedness, abstention quality, latency, and failures before
advanced policies become default.

## Risks / Trade-offs

- [Mandatory filters may reduce recall] → Treat security filters as non-negotiable and
  improve permitted corpus coverage rather than relaxing policy.
- [Hybrid retrieval and reranking increase latency] → Use parallel prefetch, bounded
  candidate budgets, batching, timeouts, fallback profiles, and evaluation-based tuning.
- [Validation-before-stream delays first token] → Favor grounded correctness in v1;
  consider provisional streaming only after a later safety review.
- [Cross-encoder availability may be limited on CPU] → Define timeout/fallback and
  evaluate a CPU-supported model before making it mandatory.
- [Citation matching can still miss subtle unsupported claims] → Require material claim
  coverage, one repair, evaluation fixtures, feedback, and abstention.
- [Answer traces can contain sensitive metadata] → Apply tenant scope, ACL-aware
  access, retention, redaction, and never store hidden reasoning or provider secrets.

## Migration Plan

1. Complete tenant, platform, and ingestion changes and verify active validated index
   generations for a tenant-owned evaluation corpus.
2. Add tenant-scoped conversation/answer-run, citation, retrieval-summary, feedback,
   and evaluation schema with additive Alembic migrations.
3. Add query settings, provider adapters, security dependencies, filters, and
   deterministic routing behind a feature flag.
4. Add hybrid retrieval, reranking, context construction, generation/validation, and
   SSE contracts with fixture-based integration tests.
5. Run a labeled evaluation set plus ACL/tenant adversarial tests before enabling the
   default route for operators.
6. Tune candidate/timeout thresholds and introduce numeric confidence only after a
   versioned calibration dataset exists.

Rollback disables the query route and preserves answer traces under retention policy.
Qdrant remains a derived store; it is never modified by a query except optional safe
cache metadata, which is tenant-scoped and disposable.

## Open Questions

- Which local cross-encoder gives acceptable CPU latency and quality for the first
  supported profile?
- What initial labeled evaluation corpus and abstention policy best represents users?
- Should the answer endpoint offer both blocking JSON and SSE in v1, or SSE only with
  clients able to collect final events?
- What retention/redaction rules apply to conversation text, answer traces, and user
  feedback in the first open-source release?
