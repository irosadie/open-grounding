## Why

The `rag-grounded-query` change shipped the default evidence path only. Graph retrieval
was explicitly deferred because traversing entity/relationship graphs adds unbounded
latency, an ACL-expansion surface area, and requires a versioned graph schema before it
can be safe. Now that the gating conditions are being formalised, this change implements
tenant- and ACL-scoped graph traversal alongside the existing dense/sparse vector
retrieval path.

## What Changes

- Add a graph traversal layer to the retrieval pipeline that operates alongside (not
  instead of) the existing hybrid vector path.
- Every hop in the traversal MUST apply the same tenant, ACL, and classification filters
  already enforced on vector retrieval.
- Traversal depth and node budget are hard-bounded per request to prevent runaway latency.
- Graph retrieval is additive: it enriches the evidence set without replacing the default
  evidence path.
- Introduce a versioned graph schema that defines entity types, relationship types, and
  the ACL predicate model applied at each hop.

## Capabilities

### New Capabilities

- `rag-graph-retrieval`: Traverse tenant- and ACL-scoped entity/relationship graphs
  alongside dense/sparse vector retrieval. Every hop enforces mandatory ACL predicates.
  Bounded traversal depth and node budget are enforced per request. Graph evidence is
  merged into the retrieval result set before the existing calibrated-evidence and
  grounded-generation steps.

### Modified Capabilities

- `rag-grounded-query` (retrieval step): Accepts an optional graph evidence set in
  addition to the existing dense/sparse vector results. Merging is additive; the rest of
  the pipeline is unchanged.

## Impact

- New: graph schema definition, per-hop ACL predicate model, traversal executor.
- Modified: retrieval coordinator to optionally invoke graph traversal and merge results.
- No changes to generation, streaming, or the calibrated-evidence decision path.
- Gating condition (must be satisfied before this change is promoted):
  - A versioned graph schema exists and is under source control.
  - Every hop in the traversal applies mandatory ACL predicates validated against the
    tenant and classification model.
  - Bounded traversal depth and node budget are enforced and documented.
