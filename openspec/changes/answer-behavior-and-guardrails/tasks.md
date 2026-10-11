## 1. Policy contracts and domain model

- [x] 1.1 Define `AnswerBehaviorProfile`, `GuardrailProfile`, effective-policy value objects, enums, and immutable version semantics in the domain layer; verify unit tests cover valid values, invalid combinations, precedence, and rollback selection.
- [x] 1.2 Define source-policy, greeting-policy, no-evidence-action, response-style, provenance-kind, and guardrail-decision shared contracts; verify TypeScript and Pydantic contract tests reject unknown values and unsafe combinations.
- [x] 1.3 Add tenant-scoped/versioned persistence models and migration tables for answer behavior, guardrails, policy versions, and policy audit records; verify migration upgrade/downgrade and tenant uniqueness tests pass.
- [x] 1.4 Seed the explicit migrated default (`DOCUMENT_MCP_GENERAL`, `ALLOW_UNGROUNDED`, `ANSWER_UNGROUNDED`, 1024 output tokens, baseline guardrails); verify existing tenants resolve a recorded version without changing unrelated data.

## 2. Effective policy API and authorization

- [x] 2.1 Implement policy repositories and an effective-policy resolver with deployment default plus knowledge-base override precedence; verify cross-tenant lookup and retired-version tests pass.
- [x] 2.2 Add ADMIN-only answer-behavior and guardrail configuration endpoints, defaults endpoints, and read-only effective-policy endpoint; verify unauthorized writes return `FORBIDDEN` and reads never expose secrets.
- [x] 2.3 Add request validation for persona length/content, style enum, output-token range, source-policy/fallback compatibility, freshness, tool budgets, and guardrail profile constraints; verify boundary tests cover all rejected combinations.
- [x] 2.4 Synchronize Pydantic schemas, shared Zod schemas, response types, API constants, and generated OpenAPI; verify contract tests and OpenAPI validation pass.

## 3. Guardrail enforcement pipeline

- [x] 3.1 Implement immutable platform guardrail baseline and additive tenant/knowledge-base profile evaluation with stable reason codes; verify profiles cannot weaken baseline rules.
- [x] 3.2 Integrate input guardrails before retrieval, planner execution, MCP invocation, generation, and memory scheduling; verify blocked requests produce no downstream side effects.
- [x] 3.3 Integrate tool guardrails with MCP permission, argument validation, per-query call count, timeout, payload, freshness, and confirmation rules; verify denied, timed-out, stale, and failed calls never become evidence.
- [x] 3.4 Integrate output guardrails before blocking response, SSE delta, async result, and assistant-message persistence; verify rejected content is never released or persisted as an answer.
- [x] 3.5 Apply policy consistently to direct, planner-enabled, planner-disabled, streaming, non-streaming, and async worker execution; verify equivalent requests produce equivalent policy decisions.
- [x] 3.6 Add redacted guardrail decision persistence/metrics with trace correlation; verify audit records contain stage/version/reason without raw secrets, prompts, or tool arguments.

## 4. Generation and provenance enforcement

- [x] 4.1 Replace hard-coded final-answer persona and source instructions with policy-aware prompt composition; verify persona cannot override safety, source, citation, tenant, or output rules.
- [x] 4.2 Pass the effective output-token budget through the generation port and enforce equivalent OpenAI and Ollama request semantics; verify provider adapter tests inspect bounded request payloads.
- [x] 4.3 Add canonical document/MCP provenance references and extend answer/citation validation to accept only selected, authorized, non-expired references; verify invalid, stale, denied, and cross-trace references are rejected.
- [x] 4.4 Enforce `DOCUMENT_ONLY`, `DOCUMENT_OR_MCP`, and `DOCUMENT_MCP_GENERAL` behavior in final answer release; verify no-evidence, unsupported-claim, greeting, and policy-conflict fixtures.
- [x] 4.5 Preserve bounded repair and validated-before-streaming behavior for both document and MCP citations; verify no rejected answer delta is emitted after schema, guardrail, or provenance failure.
- [x] 4.6 Record effective policy version, guardrail version, source kinds, budget, provider/model, and safe provenance metadata in answer traces; verify trace output excludes hidden reasoning and credentials.

## 5. MCP answer-source integration

- [x] 5.1 Normalize successful MCP results into bounded provenance references containing server, tool, invocation, trace, timestamp, and freshness metadata; verify result bounds and tenant ownership.
- [x] 5.2 Keep MCP results isolated as untrusted context and prevent tool text from modifying prompts, policy, authorization, or guardrails; verify prompt-injection tool fixtures remain blocked.
- [x] 5.3 Add safe MCP provenance fields to blocking/SSE response contracts and frontend citation/source models; verify denied, stale, and failed tool results are omitted from answer evidence.
- [x] 5.4 Update MCP audit records and retention behavior for answer-linked invocation identity without persisting raw arguments or credentials; verify admin audit queries remain tenant-scoped.

## 6. Console and user-facing behavior

- [x] 6.1 Add answer-behavior and guardrail settings pages/forms with inherited-vs-local values, active version, validation errors, and ADMIN-only writes; verify non-admin users see read-only effective policy.
- [x] 6.2 Add transaction hooks, query keys, shared labels, and cache invalidation for policy configuration; verify save, activate, retire, rollback, and stale-cache flows.
- [x] 6.3 Render grounded document, MCP-supported, general/non-grounded, abstained, refused, and operational-failure states distinctly; verify general and MCP results cannot be labeled as document-grounded.
- [x] 6.4 Keep streaming and non-streaming UI semantics identical for route, policy label, provenance, limitations, and citations; verify SSE tests cover validated-only deltas.

## 7. Evaluation, documentation, and verification

- [x] 7.1 Add policy-matrix fixtures for every source policy, greeting policy, guardrail stage, provider, token budget boundary, MCP state, streaming mode, async mode, and tenant boundary; verify fixture results are deterministic.
- [x] 7.2 Add regression tests for current LLM-first behavior and strict document/MCP modes, including planner GENERAL-task denial and client policy override rejection; verify all affected API tests pass.
- [x] 7.3 Add OpenAPI examples, effective-policy documentation, operator runbook, migration/rollback guidance, and updated architecture/status docs; verify docs no longer claim implemented features are unavailable.
- [x] 7.4 Run backend and frontend targeted tests, schema/OpenAPI validation, lint/type checks, and migration checks; verify no unrelated working-tree changes are included in the implementation diff.
- [x] 7.5 Perform a production-readiness review covering authorization, redaction, fail-closed behavior, provider budget enforcement, trace retention, rollback, and cross-tenant isolation; verify the review checklist is attached to the change before archive.
