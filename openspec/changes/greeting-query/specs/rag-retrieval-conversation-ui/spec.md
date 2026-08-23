## MODIFIED Requirements

### Requirement: The UI distinguishes answer availability from evidence provenance

The retrieval conversation UI SHALL render a safe answer even when `evidenceLevel` is `none`. It MUST show that the answer is not grounded in the selected knowledge bases when no validated evidence supports it, and MUST NOT show the existing abstention warning solely because evidence is absent. It SHALL show citations only when they are returned by the server.

The UI SHALL render a guardrail refusal as a refusal state without displaying rejected answer content. Grounded answers SHALL continue to show their evidence level and document citations.

#### Scenario: Safe answer without selected-document evidence

- **WHEN** the API returns an answered/non-grounded route with answer text, `evidenceLevel: none`, and an empty citation list
- **THEN** the UI displays the answer normally, labels it as not grounded in the selected knowledge bases, and does not display an abstention card

#### Scenario: Grounded answer

- **WHEN** the API returns a grounded route with validated evidence and citations
- **THEN** the UI displays the answer, evidence level, and only the supplied citations

#### Scenario: Guardrail refusal

- **WHEN** the API returns a refused route with no answer content
- **THEN** the UI displays a safe refusal state and does not render a rejected answer or fabricated citations

#### Scenario: No hard-coded greeting presentation

- **WHEN** a greeting is returned as a normal safe LLM answer
- **THEN** the UI renders it using the same answer path as any other non-grounded answer, without a greeting-specific route or hard-coded text
