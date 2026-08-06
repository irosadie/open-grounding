## Context

`rag-grounded-query` ships the default evidence path: tenant- and ACL-scoped hybrid
(dense + sparse) retrieval, calibrated-evidence decisions, grounded generation, and SSE
streaming. Graph traversal was deferred with an explicit gating condition: a versioned
graph schema must exist and every hop must enforce mandatory ACL predicates.

This design document describes how graph retrieval integrates into the existing pipeline
once those gating conditions are met.

## Goals / Non-Goals

**Goals:**

- Traverse entity/relationship graphs alongside (not instead of) hybrid vector retrieval.
- Enforce the same tenant, ACL, and classification filters at every graph hop as are
  applied to vector retrieval.
- Hard-bound traversal depth and node budget per request.
- Merge graph evidence additively into the retrieval result set before the existing
  calibrated-evidence and grounded-generation steps.
- Define a versioned graph schema (entity types, relationship types, ACL predicate model).

**Non-Goals:**

- Replace the default dense/sparse evidence path.
- Relax tenant, classification, or active-generation filters at any hop.
- Implement autonomous multi-hop planning (that is `rag-query-decomposition`).
- Persist graph traversal state across sessions (that is `rag-conversation-memory`).

## Decisions

### Graph traversal is additive, not a replacement

The default hybrid retrieval path remains the primary evidence source. Graph traversal
enriches the evidence set. If graph traversal fails or returns nothing, the pipeline
falls back to vector results only without surfacing an error to the caller.

### ACL predicates are mandatory at every hop

Every hop applies the same tenant, ACL, and classification predicates enforced on vector
retrieval. An entity outside tenant, ACL, or classification scope is excluded together
with all downstream hops. No partial ACL relaxation is permitted.

### Traversal depth and node budget are hard-bounded

A maximum hop depth (e.g. 3) and a maximum node count per request (e.g. 50) are
enforced. Exceeding either truncates the traversal and records the truncation in the
trace. These bounds are configurable but cannot be removed.

### Versioned graph schema is a prerequisite

The graph schema (entity types, relationship types, per-type ACL predicate) is versioned
under source control. The traversal executor validates the schema version at startup and
refuses to run against an unknown schema version.

### Graph evidence is merged before calibrated-evidence decisions

Graph-retrieved nodes are converted to the same evidence format as vector results and
merged into the retrieval result set. The existing calibrated-evidence and
grounded-generation steps operate on the merged set without knowing the evidence source.

## Architecture

```
Query
  → Retrieval Coordinator
      ├─ Dense/Sparse Vector Retrieval (existing)
      └─ Graph Traversal Executor (new, optional)
          ├─ Schema version check
          ├─ Hop 1: seed from vector results, apply ACL predicates
          ├─ Hop N: expand neighbours, apply ACL predicates, check depth/budget
          └─ Convert graph nodes → evidence format
  → Merge (additive)
  → Calibrated-Evidence Decision (existing, unchanged)
  → Grounded Generation (existing, unchanged)
  → SSE Streaming (existing, unchanged)
```

## Risks / Trade-offs

- [Latency] Graph traversal adds per-hop latency. Hard depth/budget bounds mitigate
  worst-case latency. Monitor p95/p99 latency after rollout.
- [ACL expansion surface] Every new hop is a new ACL check. The mandatory-predicate rule
  and bounded budget limit the expansion surface but must be audited on schema changes.
- [Schema drift] Graph schema changes may break traversal or silently exclude entities.
  Schema versioning and startup validation are the primary mitigations.
- [Empty graph] If no graph schema is installed the traversal executor is a no-op and the
  pipeline runs on vector results only. This is the expected state before the gating
  condition is met.

## Open Questions

- What graph store is used (e.g. embedded, external)? Deferred to implementation.
- What is the optimal seed strategy — seed from top-K vector results or from the query
  entities directly? Deferred to implementation evaluation.
- What are the initial depth and node budget defaults? To be validated against latency
  benchmarks in the implementation change.
