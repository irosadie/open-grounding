## 1. Prerequisites (gating conditions — must be satisfied before implementation)

- [ ] 1.1 Define and version-control the graph schema (entity types, relationship types, per-type ACL predicate model).
- [ ] 1.2 Validate that ACL predicates on every hop are compatible with the existing tenant and classification model.
- [ ] 1.3 Establish and document traversal depth and node budget defaults via latency benchmarks.

## 2. Core implementation

- [ ] 2.1 Implement the graph traversal executor (schema version check, hop loop, ACL predicate enforcement, depth/budget bounds).
- [ ] 2.2 Implement graph node → evidence format conversion.
- [ ] 2.3 Extend the retrieval coordinator to optionally invoke graph traversal and merge results additively.
- [ ] 2.4 Record traversal truncation events in the existing trace/audit log.

## 3. Fallback and safety

- [ ] 3.1 Implement no-op fallback when no versioned graph schema is installed.
- [ ] 3.2 Implement fallback to vector-only results on unknown schema version, with logged version mismatch.
- [ ] 3.3 Verify that the generation, calibrated-evidence, and streaming steps are unchanged.

## 4. Tests

- [ ] 4.1 Unit test: hop crossing unauthorized boundary is excluded with all downstream hops.
- [ ] 4.2 Unit test: traversal truncated at max depth; truncation recorded in trace.
- [ ] 4.3 Unit test: traversal truncated at max node budget; truncation recorded in trace.
- [ ] 4.4 Unit test: no-op when no graph schema installed; pipeline uses vector results only.
- [ ] 4.5 Unit test: refusal and fallback on unknown schema version.
- [ ] 4.6 Integration test: graph evidence merged additively; generation step unchanged.

## 5. Docs and promotion

- [ ] 5.1 Document graph schema format and versioning contract.
- [ ] 5.2 Document traversal depth and node budget configuration.
- [ ] 5.3 Update `rag-grounded-query` retrieval step spec to reference optional graph evidence input.
- [ ] 5.4 Run `openspec validate` and confirm all delta specs pass.
