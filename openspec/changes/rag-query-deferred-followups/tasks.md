## 1. Establish deferred capability specifications

- [x] 1.1 Write design document for deferred query capabilities and gating conditions.
- [x] 1.2 Define rag-graph-retrieval target spec with per-hop ACL gating.
- [x] 1.3 Define rag-live-tool-execution target spec with sandbox, permission, and audit gating.
- [x] 1.4 Define rag-query-decomposition target spec with evaluation-gated opt-in behavior.
- [x] 1.5 Define rag-conversation-memory target spec with retention/redaction and opt-in gating.
- [x] 1.6 Define rag-numeric-confidence target spec with labeled calibration dataset gating.
- [x] 1.7 Validate all deferred capability deltas pass `openspec validate`.

## 2. Tracked future implementation (each becomes its own change when gated)

- [ ] 2.1 Create implementation change for graph retrieval when a versioned graph schema and per-hop ACL predicate model are available.
- [ ] 2.2 Create implementation change for live tool execution when a sandbox, per-tenant permission model, and audit trail are available.
- [ ] 2.3 Create implementation change for multi-hop decomposition when an evaluation set proves recall improvement without degrading groundedness.
- [ ] 2.4 Create implementation change for long-term memory when a retention/redaction policy and explicit opt-in model are available.
- [ ] 2.5 Create implementation change for numeric confidence when a versioned labeled calibration dataset and abstention threshold are validated.
