## Context

The `rag-grounded-query` change shipped the default evidence path only. Five advanced
behaviors were explicitly excluded and recorded as non-goals so the first release could
stay safe, bounded, observable, and reproducible. This change establishes target
specifications and gating conditions for each deferred item so future implementation
changes can be created against a reviewed baseline rather than from memory.

## Goals / Non-Goals

**Goals:**

- Document the target behavior and gating condition for each of the five deferred
  capabilities (graph retrieval, live tool execution, multi-hop decomposition,
  long-term memory, numeric confidence).
- Keep the deferred work visible as an active tracker so it is not silently lost.

**Non-Goals:**

- Implement any of the five deferred capabilities. Each remains deferred until its
  gating condition is met and a separate implementation change is reviewed.
- Change the default query route, retrieval, generation, or streaming behavior
  shipped by `rag-grounded-query`.

## Decisions

### Each deferred item is its own capability spec

Graph retrieval, live tools, decomposition, long-term memory, and numeric confidence
are distinct concerns with distinct gating conditions. Documenting each as a separate
capability spec keeps the target behavior and gating condition localized and lets a
future implementation change reference a single capability.

### Target specs describe behavior, not implementation

The deferred capability specs describe WHAT each capability SHALL do and the condition
that MUST be met before it is promoted to default. They deliberately defer HOW until a
gated implementation change is proposed. This lets the specs exist now without
pre-committing to a specific vendor, model, or architecture.

### Gating conditions are mandatory and explicit

No deferred capability may become default behavior until its documented gating
condition is satisfied and reviewed. This prevents a future change from quietly
reintroducing unbounded latency, ACL bypass, hidden reasoning, or uncalibrated
confidence.

## Risks / Trade-offs

- [Specs for unimplemented capabilities may drift] -> Review each spec when a gated
  implementation change is proposed and update target behavior against real constraints.
- [Gating conditions may be too strict or too loose] -> Treat gating conditions as
  living constraints revisited per implementation change.
- [A tracker that never ships] -> Each item has an explicit gating condition so progress
  is measurable; an item whose gating condition is never met is intentionally deferred,
  not silently abandoned.

## Open Questions

- Which graph schema and per-hop ACL predicate model best fits the existing tenant and
  knowledge-base boundaries before graph retrieval is gated?
- What sandbox and permission model is acceptable for live tool execution in a
  single-deployment open-source release?
- What labeled calibration corpus best represents abstention and grounding trade-offs
  before numeric confidence is gated?
