## Why

The query console currently treats the absence of validated knowledge-base evidence as a reason to abstain. That makes harmless inputs such as `hi`, and any other question with no matching document, fail before the LLM can answer. A hard-coded greeting route would only patch one symptom and would not match the intended product behavior.

The system should be LLM-first: retrieval supplies grounding when it is available, while guardrails—not evidence availability—decide whether a request must be refused.

## What Changes

- Remove hard-coded greeting detection and the dedicated `greeting` route.
- Run configured guardrails before and around generation; a guardrail refusal is the only content-level refusal path.
- Make knowledge-base retrieval optional for answering: the LLM can answer with no retrieved evidence and must not fabricate citations.
- Distinguish grounded answers from ungrounded/general answers using route and evidence metadata rather than treating `evidenceLevel: none` as abstention.
- Keep factual answers with validated evidence citation-bound and preserve the existing tenant, authorization, admission, and policy controls.
- Update the API contract, SSE events, frontend rendering, traces, and tests together.

## Capabilities

### New Capabilities

### Modified Capabilities

- `rag-query-security-and-planning`: Query execution becomes LLM-first with optional evidence and explicit guardrail refusal.
- `rag-retrieval-conversation-ui`: The console renders an answer without evidence as a normal, clearly marked answer and reserves refusal UI for guardrail denials.

## Impact

- **API domain/service**: Remove greeting-specific planning and allow generation with an empty or partial evidence context after guardrails pass.
- **Answer contract**: Add explicit non-grounded and refusal outcomes, keep evidence and citations orthogonal to whether an answer exists, and remove the greeting-only route.
- **Generation/validation**: Support answers that do not contain document claims while retaining strict citation validation for grounded answers.
- **Frontend**: Stop converting `evidenceLevel: none` into an abstention when an answer is present; show grounding status and guardrail refusal separately.
- **Tests/OpenAPI**: Cover greetings, general questions, grounded questions, no-evidence fallback, guardrail refusal, SSE, and synchronized contracts.
