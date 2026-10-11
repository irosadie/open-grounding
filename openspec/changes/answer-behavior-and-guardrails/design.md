## Context

The current query path already has tenant-scoped admission, document evidence
retrieval, structured answer parsing, answer validation, conversation history, planner
tasks, MCP invocation, SSE release, and trace persistence. Final-answer behavior is not
yet a first-class policy: the adapter owns a hard-coded system prompt, the generation
service decides between grounded and general instructions, settings contain deployment
budgets, planner `guardrails` contain planner-specific values, and MCP results are
supplementary non-citable text. The working tree also contains completed LLM-first and
greeting behavior that must become an explicit, reproducible contract.

See `proposal.md` for motivation and the delta specs for observable behavior.

## Goals / Non-Goals

**Goals:**

- Make answer behavior and guardrails explicit, versioned, tenant-safe, and
  knowledge-base aware.
- Enforce source policy and greeting policy in the service pipeline rather than relying
  on model instructions.
- Preserve structured answers, citation validation, safe streaming, tenant isolation,
  and bounded conversation/memory behavior.
- Give MCP results traceable provenance when policy permits them to support an answer.
- Apply equivalent output-token semantics to every generation provider.
- Make policy versions, guardrail decisions, provenance, and rollout quality observable.

**Non-Goals:**

- Allowing end users to submit arbitrary system prompts or per-request safety overrides.
- Replacing the existing document ingestion, retrieval, authorization, or MCP transport
  implementations.
- Exposing hidden reasoning, raw provider credentials, raw MCP arguments, or unbounded
  source/tool payloads.
- Making general knowledge the default for strict policies.
- Adding autonomous background agents or unrestricted tool chaining.

## Decisions

### 1. Separate answer behavior from guardrails

Use two policy families with independent versioning:

- `AnswerBehaviorProfile`: persona, response style, output budget, source policy,
  greeting policy, no-evidence action, citation requirement, and MCP eligibility.
- `GuardrailProfile`: immutable baseline plus additive input, tool, and output rules.

The effective policy is resolved in this order:

```text
immutable platform safety baseline
  → deployment/tenant defaults
  → knowledge-base answer behavior override
  → knowledge-base guardrail additions
```

The query payload, planner output, retrieved content, memory, and MCP result cannot
change this order. A profile is immutable after activation; updates create a new version.
This keeps rollback and trace reproduction possible. A single combined JSON blob was
rejected because it would mix user-facing style with security-critical policy and make
independent review and rollback difficult.

### 2. Keep source policy separate from persona

`source_policy` is a typed enum, not a free-form prompt instruction:

| Policy | Allowed support | No-evidence behavior |
|---|---|---|
| `DOCUMENT_ONLY` | Authorized selected document evidence | `ABSTAIN` or `REFUSE` |
| `DOCUMENT_OR_MCP` | Authorized documents or validated MCP evidence | `ABSTAIN` or `REFUSE` |
| `DOCUMENT_MCP_GENERAL` | Documents, MCP, or explicitly non-grounded general knowledge | `ANSWER_UNGROUNDED` permitted |

`greeting_policy` is evaluated independently, so a deployment can be strict for factual
questions while explicitly allowing safe conversational greetings. If a greeting is
allowed without evidence, the response is still labeled non-grounded and follows all
guardrails.

### 3. Enforce policy at three service boundaries

The query pipeline becomes:

```text
admission
  → effective policy resolution
  → input guardrails
  → query/planner policy filtering
  → document retrieval and/or MCP execution
  → evidence/provenance assembly
  → policy-aware generation
  → output guardrails
  → schema/citation/provenance validation
  → trace persistence and response/SSE release
```

Input, tool, and output guardrails are independent checks. A failure is fail-closed for
the affected stage. In particular, a failed output check cannot be converted into a
normal ungrounded answer, and a denied MCP result cannot become supplementary evidence.

### 4. Use one canonical evidence/provenance reference model

Document and MCP support are represented internally by a common reference shape with:

- `source_kind`: `DOCUMENT` or `MCP`;
- stable source identity and locator;
- tenant and query/trace identity;
- selected/authorized status;
- produced-at and expiry/freshness metadata;
- bounded snippet or result digest for trace and UI use.

Document citations keep their existing `S1`, `S2`, ... identifiers. MCP references use
an explicit namespace such as `M1`, `M2`, ... and resolve to safe server/tool/invocation
metadata. Raw tool arguments and credentials never enter the reference or answer trace.
The generator still receives untrusted source blocks; provenance validation is performed
outside the model before release.

### 5. Make token budgets provider-neutral and effective

The answer policy owns `max_output_tokens`; deployment settings own the hard maximum.
The effective value is:

```text
min(profile.max_output_tokens, deployment_max_output_tokens, provider_model_maximum)
```

The generation port carries this value. The OpenAI adapter maps it to its completion
budget field, while the Ollama adapter maps it to its bounded generation option. If a
provider cannot express or verify the limit, the adapter returns a bounded operational
failure instead of silently falling back to an unbounded request. The existing context
budget continues to reserve the effective output budget before selecting document
evidence.

### 6. Treat persona as a constrained generation input

Prompt composition order is fixed:

```text
platform safety and output contract
  → effective source/guardrail policy
  → administrator persona and style
  → validated conversation history
  → untrusted document/MCP/memory context
  → current user question
```

Persona text is length-bounded, stored as configuration data, and cannot override higher
priority policy. Retrieved documents, memory, and tool results are always delimited as
untrusted data. The structured answer schema remains the release contract; persona does
not get to change citation or safety fields.

### 7. Provide explicit API and UI surfaces

Use tenant-scoped, knowledge-base-aware endpoints consistent with existing config
surfaces:

- `GET/POST/DELETE /rag/knowledge-bases/{id}/answer-behavior`;
- `GET /rag/knowledge-bases/{id}/answer-behavior/defaults`;
- `GET/POST/DELETE /rag/knowledge-bases/{id}/guardrails`;
- `GET /rag/knowledge-bases/{id}/effective-answer-policy` (read-only effective merge).

All writes require ADMIN access, create a new version, and return only non-secret policy
metadata. The console exposes editable fields only for writable endpoints and shows the
effective inherited values separately from local overrides. Query APIs receive no policy
write fields; response and SSE metadata expose route, evidence level, provenance kind,
policy version, and safe limitations.

### 8. Migrate current behavior explicitly

The migration creates a versioned deployment default that preserves the current working
tree behavior unless the operator chooses a stricter policy:

- `source_policy=DOCUMENT_MCP_GENERAL`;
- `greeting_policy=ALLOW_UNGROUNDED`;
- `no_evidence_action=ANSWER_UNGROUNDED`;
- `max_output_tokens=1024`;
- baseline input/tool/output guardrails enabled.

Existing knowledge bases inherit this version until an administrator creates an override.
Rollback activates a prior validated version and retains all historical versions and
audit events. If the effective policy cannot be loaded, the query fails safely rather
than silently reverting to hard-coded permissive behavior.

### 9. Roll out with policy-matrix evaluation

Before activation, the system evaluates each policy combination against fixtures for
grounded claims, unsupported claims, greetings, prompt injection, secret extraction,
MCP success/denial/staleness, token budgets, streaming, async execution, and provider
failure. A policy version can be activated only after passing required checks. Trace and
metrics use stable reason codes and redaction rules so operators can investigate without
persisting sensitive payloads.

## Risks / Trade-offs

- **[Risk] A strict policy can turn previously answered queries into abstentions** →
  Preserve current behavior through an explicit migrated default and make policy changes
  visible with effective-policy and limitation metadata.
- **[Risk] MCP data can be stale or instruction-injected** → Treat MCP results as
  untrusted, enforce freshness and payload bounds, and validate provenance outside the
  model before release.
- **[Risk] Provider token semantics differ** → Keep budgets in the generation port, use
  provider-specific mappings in adapters, verify usage where available, and fail safely
  when enforcement is impossible.
- **[Risk] Policy configuration can become a new security boundary** → Require ADMIN
  writes, immutable versions, additive guardrails, tenant predicates, audit events, and
  cross-tenant tests.
- **[Risk] Existing specs/docs describe the pre-LLM-first behavior** → Update OpenAPI,
  main specs, architecture docs, and regression fixtures in the same change.

## Migration Plan

1. Add policy/profile tables, immutable version fields, indexes, and the explicit migrated
   default without changing the existing query response contract.
2. Add effective-policy read/write endpoints, schemas, authorization, and OpenAPI output.
3. Integrate policy resolution and staged guardrails in shadow/record-only mode; compare
   decisions with current behavior using the policy matrix.
4. Add provider budget enforcement and canonical document/MCP provenance validation.
5. Enable enforcement for the migrated default, then expose per-knowledge-base overrides
   to administrators.
6. Roll back by activating the previous policy version or disabling the feature flag;
   never delete historical policy or audit records.

## Open Questions

None. `response_style` is a fixed validated enum in this change; more specialized style
guidance belongs in the bounded persona instruction and does not create a second style
configuration channel.
