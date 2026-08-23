## MODIFIED Requirements

### Requirement: Admitted requests are LLM-first and guardrail-bounded

The system SHALL enforce authentication, tenant isolation, server-derived knowledge-base authorization, configured rate/token/payload/concurrency limits, and policy checks before generation. After those controls and configured guardrails pass, the system SHALL attempt an LLM answer even when retrieval returns no validated evidence. Missing or low-quality evidence MUST NOT by itself produce an abstention or refusal.

The response MUST distinguish provenance from answer availability. It SHALL expose a grounded outcome when the answer is supported by validated selected evidence, a non-grounded answered outcome when the LLM safely answers without sufficient selected evidence, and a refused outcome when guardrails reject the request. Non-grounded answers MUST NOT contain fabricated document citations or claim to be supported by unavailable evidence.

The system MUST NOT use a hard-coded greeting phrase list or a greeting-specific route to decide whether a request can be answered.

#### Scenario: Greeting is answered through the normal LLM path

- **WHEN** an authenticated user submits `hi`, `hello`, or another safe conversational input
- **THEN** the request reaches the normal LLM generation path, returns a safe answer, and is not rejected merely because retrieval has no matching chunks

#### Scenario: Safe question has no validated evidence

- **WHEN** an authenticated user submits a safe question and retrieval returns no validated evidence
- **THEN** the server still returns an LLM answer with a non-grounded/answered outcome, an evidence level of `none`, and no fabricated citations

#### Scenario: Safe question has validated evidence

- **WHEN** retrieval returns authorized validated evidence and the generated answer passes evidence-bound validation
- **THEN** the server returns a grounded outcome with citations limited to the authorized selected evidence

#### Scenario: Guardrail rejects a request

- **WHEN** configured guardrails reject the input or the generated answer
- **THEN** the server returns a refused outcome with no answer content and records the guardrail decision without exposing protected policy details

#### Scenario: Greeting text is combined with a substantive question

- **WHEN** a user submits a message such as `hi, what is the retention policy?`
- **THEN** the message follows the same normal LLM path as every other safe query; it is not classified by a hard-coded greeting rule
