## Context

The current RAG pipeline requires validated retrieval evidence before it calls the generator. When retrieval returns no chunks, the service returns `abstain`, and the frontend treats every completed response with `evidenceLevel: none` as an abstention. This incorrectly conflates grounding quality with the ability to answer conversationally.

The desired behavior is an LLM-first query assistant. The selected knowledge bases remain important sources of evidence, but they are not a prerequisite for a response. A request should be refused only when the configured guardrails reject it.

## Goals / Non-Goals

**Goals:**

- Let the LLM answer greetings, general questions, and knowledge-base questions through one normal generation path.
- Use retrieved evidence when available and preserve citations for claims supported by that evidence.
- Return a clearly labeled non-grounded answer when no validated evidence is available, without fabricated citations.
- Make guardrail refusal explicit and distinct from missing or low-quality retrieval evidence.
- Preserve tenant isolation, server-derived authorization, rate limits, payload limits, concurrency limits, and existing policy checks.
- Keep trace, conversation, SSE, API schema, and UI states consistent.

**Non-Goals:**

- No hard-coded greeting phrase list or intent-specific answer branch.
- No removal of authentication, authorization, tenant isolation, or request admission controls.
- No presentation of an ungrounded answer as document-grounded.
- No weakening of citation validation when the answer claims to rely on retrieved documents.

## Decisions

### 1. Separate guardrails from evidence gating

Admission, authorization, and configured guardrails run before generation. If they pass, lack of retrieval evidence is not a refusal condition. Retrieval and evidence scoring describe answer provenance and confidence; they do not decide whether the LLM may respond.

### 2. Use one LLM generation path with optional evidence

The generation port and prompt contract will accept an optional evidence context. The LLM receives the selected evidence when retrieval succeeds and can still answer when the context is empty. The prompt must require the model to distinguish document-supported claims from general knowledge and never invent citations.

### 3. Make answer route and evidence level orthogonal

The response contract will distinguish at least:

- `grounded`: an answer passed the evidence-bound validation path and has document citations where required.
- `answered`: the LLM returned a safe answer without sufficient validated document evidence; citations remain empty and the response states that it is not grounded in the selected documents.
- `refused`: a guardrail rejected the request; no answer is returned.

Existing `clarify` or operational failure behavior may remain where required by current contracts, but `abstain` must no longer be used merely because retrieval returned no evidence.

### 4. Apply answer validation according to provenance

Grounded answers continue to use the existing citation and evidence validation. Non-grounded answers use a safety/content validation path that does not require document citations. A failed safety validation becomes `refused`; a failed evidence validation does not automatically erase an otherwise safe general answer.

### 5. Keep the UI honest about provenance

The UI will render an `answered` response normally, show an explicit “not grounded in selected knowledge bases” status, and omit citations when none exist. It will show a refusal state only for `refused`. `evidenceLevel: none` by itself must never trigger the abstention warning when an answer is present.

### 6. No special handling for greetings

Greetings are ordinary input to the same LLM path. This avoids brittle phrase lists and allows the model to handle natural variations without adding routes or deterministic answer text.

## Risks / Trade-offs

- **[Risk] Ungrounded answers can be inaccurate** → Label provenance clearly, instruct the LLM not to imply document support, and retain grounded validation when evidence is used.
- **[Risk] A weak guardrail could allow unsafe content** → Keep guardrails explicit in the trace and test refusal cases at both pre-generation and post-generation boundaries.
- **[Risk] Providers may fail or be unavailable** → Surface an operational error/limitation distinctly from a content abstention; do not mislabel it as missing evidence.
- **[Risk] Contract changes affect multiple surfaces** → Update Pydantic, shared TypeScript, SSE, UI, trace persistence, and tests in one change.

## Migration Plan

First align the response contract and generation/guardrail interfaces, then remove the hard-coded greeting implementation and route all admitted queries through the optional-evidence generation path. Deploy API and frontend together. Verify `hi`, a general question, a grounded knowledge-base question, a question with no matching evidence, and a guardrail refusal. Rollback is a code revert; existing tenant and policy boundaries remain unchanged.
