## 1. Prerequisites, query contracts, and trace schema

- [ ] 1.1 Verify tenant, platform, and ingestion changes are implemented with active validated document/index generations, tenant context, Qdrant payload indexes, provider ports, and evaluation fixtures.
- [ ] 1.2 Add validated query/retrieval/generation settings for budgets, rate/concurrency limits, timeouts, profile IDs, feature flags, retention, and one bounded retry/repair policy.
- [ ] 1.3 Add additive tenant-scoped schema and Alembic migrations for conversations, answer runs, retrieval summaries, selected evidence, citations, validation outcomes, feedback, and evaluation results.
- [ ] 1.4 Add domain models, repository protocols, and SQLAlchemy implementations that retain safe reproducibility metadata without hidden reasoning, provider secrets, or unnecessary raw source duplication.

## 2. Query security, preprocessing, and routing

- [ ] 2.1 Add Pydantic and FastAPI contracts for blocking and SSE query requests that prohibit client-controlled tenant, ACL, clearance, active-generation, and raw vector-filter inputs.
- [ ] 2.2 Implement authenticated tenant/knowledge-base authorization, RBAC/ABAC resolution, rate/token/payload/concurrency limits, and server-side mandatory filter construction.
- [ ] 2.3 Implement input guardrails, language/whitespace normalization, bounded recent conversation window, original/standalone query traces, and deterministic grounded/clarify/abstain routing.
- [ ] 2.4 Add HTTP-contract, unit, and adversarial tests for tenant/ACL override attempts, unavailable knowledge bases, policy denials, and bounded query-rewrite behavior.

## 3. Hybrid retrieval, fusion, and ranking

- [ ] 3.1 Implement tenant-aware query dense/sparse representation adapters using active compatible model/index profiles and bounded provider failure handling.
- [ ] 3.2 Implement parallel Qdrant dense and sparse retrieval with identical mandatory payload filters, profile-configured candidate budgets, and no post-filter security boundary.
- [ ] 3.3 Implement RRF fusion, superseded/exact/near-duplicate removal, source-diversity/MMR selection, and deterministic candidate trace records.
- [ ] 3.4 Implement cross-encoder reranking with batching, truncation, timeout, version tracing, and deterministic fallback without relaxing evidence filters.
- [ ] 3.5 Implement explainable high/medium/low/none evidence gate with at most one retrieval retry, clarification, or abstention; defer numeric confidence until calibration exists.
- [ ] 3.6 Add disposable integration tests for ACL/classification/time filters, dense-sparse overlap, reranker failure, diversity behavior, and low-evidence abstention.

## 4. Evidence context, grounded answer, and SSE

- [ ] 4.1 Implement canonical chunk/source fetch, repeat ACL checks, permitted parent expansion, token/output reserves, deduplication, source isolation, and stable citation assignment.
- [ ] 4.2 Implement evidence-bound generation port/adapters and internal answer schema that distinguishes source facts, inferences, conflicts, limitations, and citation references.
- [ ] 4.3 Implement schema, citation, material-claim coverage, contradiction, policy/PII, and format validation with one bounded repair or safe abstention.
- [ ] 4.4 Implement blocking JSON and SSE response contracts/events; stream only validated final deltas and final citations, evidence level, limitations, and trace ID.
- [ ] 4.5 Add end-to-end tests for supported answers, invalid citation repair, source prompt-injection isolation, inaccessible parent exclusion, generation timeout, and SSE event ordering.

## 5. Evaluation, operations, and verification

- [ ] 5.1 Implement answer-run persistence, tenant-scoped feedback, retention-aware trace access, and bounded metrics/audits for every query stage and outcome.
- [ ] 5.2 Add labeled evaluation fixtures and runner for retrieval recall, citation correctness/coverage, groundedness, abstention quality, latency, and failure rate; require evidence before promoting advanced profile changes.
- [ ] 5.3 Document query profiles, security/filter guarantees, SSE contract, evidence levels, abstention behavior, retention/redaction, debugging, and operator evaluation workflow.
- [ ] 5.4 Regenerate FastAPI OpenAPI and run unit, HTTP-contract, PostgreSQL, Qdrant, provider-adapter, SSE, security, and full repository quality checks.
- [ ] 5.5 Record deferred graph/tool/decomposition/long-term-memory/numeric-confidence work as follow-up changes.
