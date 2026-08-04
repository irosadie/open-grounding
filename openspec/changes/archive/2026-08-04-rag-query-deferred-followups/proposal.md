## Why

The `rag-grounded-query` change shipped the default evidence path only: tenant- and
ACL-scoped hybrid retrieval, calibrated-evidence decisions, grounded generation with
validation, and SSE streaming. Several advanced behaviors were deliberately excluded
and called out as non-goals so the first release could stay safe, bounded, observable,
and reproducible. They must not be silently forgotten: each deferred item is recorded
here as an explicit follow-up change with the reason it was deferred and the condition
that must be met before it is promoted.

## What Changes

This change is a tracking proposal. It does not implement code. It records five deferred
follow-up items so they can be picked up as independent, separately-reviewed changes
once their gating conditions are met:

- **Graph retrieval** — Traverse entity/relationship graphs alongside dense/sparse
  vector retrieval. Deferred because the first release supports the default evidence
  path only and graph traversal adds unbounded latency and ACL-expansion surface area.
  Gating condition: a versioned graph schema, mandatory ACL predicates on every hop,
  and bounded traversal budgets.
- **Live tool execution** — Allow the query planner to call external tools, web search,
  database, or transactional systems. Deferred because live tools break reproducibility
  and require sandboxing, permission scoping, and audit before they can be safe.
  Gating condition: a tool permission model, execution sandbox, and per-tenant audit.
- **Automatic multi-hop decomposition** — LLM-driven multi-query, HyDE, step-back, or
  multi-hop planning as default behavior. Deferred because the v1 planner is
  deterministic and bounded; an LLM planner risks unbounded loops and hidden reasoning.
  Gating condition: an evaluation set proving decomposition improves recall without
  degrading groundedness, plus a hard bound on decomposition depth.
- **Long-term memory and autonomous agents** — Persist user preferences, run background
  agents, or store retrieved content as memory. Deferred because conversation context
  is bounded and never written to long-term memory in v1, and autonomous action is out
  of scope. Gating condition: a retention/redaction policy and an explicit opt-in model.
- **Numeric confidence calibration** — Emit a calibrated numeric confidence score with
  each answer. Deferred because a raw vector score is not confidence and a numeric score
  must be calibrated against labeled data before it can be trusted. Gating condition: a
  versioned labeled evaluation corpus that calibrates the score and an abstention
  threshold validated against it.

## Capabilities

### New Capabilities

None yet. Each follow-up item above will become its own capability and change proposal
when its gating condition is met. Promoting any item requires labeled evaluation
evidence and a separate spec before it becomes default behavior.

### Modified Capabilities

None. This change only records deferred work; it touches no capability specification.

## Impact

- No code, schema, migration, endpoint, or spec is modified by this change.
- It exists solely to prevent the deferred items from being lost: future changes that
  propose graph retrieval, live tools, decomposition, long-term memory, or numeric
  confidence must reference this record and satisfy their gating condition before
  becoming default.
- The `rag-grounded-query` proposal's "Exclude" and "Non-Goals" sections remain
  authoritative until a follow-up change supersedes them with reviewed specs.
