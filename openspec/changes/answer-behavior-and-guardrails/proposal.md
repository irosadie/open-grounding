## Why

Final-answer behavior is currently split between hard-coded adapter prompts, query
orchestration, planner configuration, and environment settings. The runtime can answer
from general knowledge and handle greetings, but operators cannot explicitly choose a
persona, output budget, source policy, or greeting policy; they also cannot enforce a
strict document/MCP-only mode. Guardrails are similarly hard-coded and are not separated
from planner configuration, while MCP output is not represented as provenance-aware
answer evidence and output-token limits are inconsistent across providers.

This needs a production-grade policy boundary so answer behavior is explicit, auditable,
tenant-scoped, provider-consistent, and fail-closed when policy or provenance cannot be
validated.

## What Changes

- Add versioned answer-behavior configuration with controlled scope and ADMIN-only
  management for persona, response style, output token budget, source policy, greeting
  policy, fallback behavior, citation requirements, and MCP eligibility.
- Add a separate versioned guardrail profile with input, tool, and output stages; define
  policy precedence, fail-closed behavior, safe refusal semantics, and audit records.
- Define explicit source policies for document-only, document-or-MCP, and
  document/MCP/general-knowledge operation. A request payload MUST NOT override these
  policies.
- Define greeting behavior independently from factual source policy, including whether a
  greeting may be answered without document or MCP evidence.
- Make final answer generation honor configured persona and bounded output budgets while
  preserving structured output, citation validation, hidden-prompt protection, and
  provider-neutral behavior.
- Make MCP results provenance-aware when they are allowed to support an answer, including
  tool identity, invocation trace, freshness, bounded result content, and validation
  rules. Strict policies MUST reject unsupported or untraceable MCP claims.
- Add API, OpenAPI, persistence, console settings, response metadata, trace, evaluation,
  migration, and regression-test coverage for the complete policy lifecycle.
- **BREAKING (semantic configuration):** deployments that do not select a policy MUST use
  an explicit migrated default rather than relying on the current hard-coded behavior.
  The migration MUST record the selected default and its version for reproducibility.

## Capabilities

### New Capabilities

- `rag-answer-behavior-config`: Versioned, scoped configuration for final-answer persona,
  style, token budgets, source policy, greeting policy, fallback, citations, and MCP use.
- `rag-answer-guardrails`: Independent input, tool, and output guardrail profiles with
  precedence, fail-closed enforcement, safe refusal, and policy-decision auditing.

### Modified Capabilities

- `rag-query-security-and-planning`: Enforce server-side source policy and greeting/fallback
  semantics across direct, planned, asynchronous, and streaming queries.
- `rag-grounded-answer-generation`: Apply answer behavior, provider-consistent token
  budgets, provenance-aware validation, bounded repair, and safe release rules.
- `rag-mcp-runtime`: Expose bounded, traceable MCP evidence metadata and enforce answer-use
  restrictions without weakening tool permission or invocation safety.
- `rag-retrieval-conversation-ui`: Add operator settings and honest user-facing labels for
  grounded, MCP-supported, general, refused, and unavailable outcomes.
- `rag-answer-evaluation-and-operations`: Persist policy/config versions, guardrail
  decisions, provenance, token usage, and evaluation dimensions needed for rollout and
  incident investigation.

## Impact

- Backend domain/application: answer-policy entities, guardrail evaluation pipeline,
  query orchestration, generation validation, MCP result normalization, and trace data.
- Persistence: tenant-scoped configuration/profile tables, immutable versions, migration
  defaults, indexes, and retention-safe policy-decision records.
- HTTP/API: ADMIN configuration endpoints, read-only effective-policy endpoint, query and
  SSE metadata, OpenAPI export, and strict server-side validation.
- Frontend: answer-policy settings, guardrail settings, effective-policy display, source
  provenance labels, refusal/abstention states, and provider budget validation.
- Providers: OpenAI and Ollama adapters must receive equivalent bounded output settings;
  provider-specific request fields remain behind the generation port.
- Operations/tests: audit and metrics, fixture-based policy matrix, migration coverage,
  cross-tenant authorization tests, and documentation/spec synchronization.
