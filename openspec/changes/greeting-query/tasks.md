## 1. OpenSpec and contract design

- [x] 1.1 Replace the greeting-only route proposal with LLM-first route/evidence semantics and explicit guardrail refusal.
- [x] 1.2 Define the API and shared type contract for grounded, non-grounded answered, clarification/operational outcomes, and refusal.

## 2. API pipeline

- [x] 2.1 Remove hard-coded greeting detection, the `greeting` route, and its deterministic answer branch.
- [x] 2.2 Run guardrails before generation and record an explicit refusal outcome when they reject a request.
- [x] 2.3 Allow the generator to run with optional/empty retrieval context after admission and guardrails pass.
- [x] 2.4 Separate grounded citation validation from non-grounded answer safety validation.
- [x] 2.5 Persist answer provenance, evidence level, citations, limitations, and guardrail decisions in the existing trace/conversation flow.

## 3. API/SSE and frontend

- [x] 3.1 Synchronize Pydantic, shared TypeScript schemas/types, SSE events, and route labels.
- [x] 3.2 Render safe non-grounded answers normally with a clear provenance label, without an abstention warning.
- [x] 3.3 Render guardrail refusals separately and never expose a rejected answer as answer content.

## 4. Tests and verification

- [x] 4.1 Add API tests for greeting/general answers, grounded answers, no-evidence answers, guardrail refusals, citation behavior, and provider failures.
- [x] 4.2 Add SSE and frontend tests for grounded, answered-without-evidence, and refused states.
- [x] 4.3 Regenerate/validate OpenAPI and run targeted API/frontend tests and static checks.
- [x] 4.4 Review the final diff for unrelated changes and confirm the old greeting-only behavior is removed.
