# rag-conversation-memory Specification Delta

## MODIFIED Requirements

### Requirement: Long-term memory is retention-aware and opt-in

The system SHALL persist bounded, durable user preferences, user-stated facts, or other future-useful user context as long-term memory only under a documented retention and redaction policy and explicit tenant opt-in. A memory-capable LLM SHALL evaluate each eligible completed conversation and return an explicit decision indicating whether a memory should be stored, together with a non-empty summary when the decision is positive. The system MUST NOT write a memory chunk when the decision is negative, the summary is empty, or the content is only a transient question, assistant-generated claim, retrieved source fact, secret, or other content excluded by the memory policy. The system MUST NOT enable autonomous background agents in this release.

#### Scenario: Memory write is not opt-in for the tenant

- **WHEN** a memory write is attempted and the tenant has not explicitly opted in
- **THEN** the system discards the memory write and continues the query without persisting any long-term memory

#### Scenario: Memory LLM rejects a conversation as not memory-worthy

- **WHEN** the memory LLM returns a negative store decision or an empty summary
- **THEN** the system MUST NOT create a memory chunk for that conversation

#### Scenario: Memory LLM accepts a durable user-stated fact

- **WHEN** an opted-in completed conversation contains a durable fact or preference explicitly stated by the user and the memory LLM returns a positive store decision with a summary
- **THEN** the system persists the bounded summary subject to the configured retention and embedding policy

#### Scenario: Retrieved source content is not treated as user memory

- **WHEN** a conversation contains a fact only because it appears in retrieved knowledge-base evidence and the user does not state or adopt it as their own durable context
- **THEN** the system MUST NOT persist that source-only fact as long-term user memory

## ADDED Requirements

### Requirement: Memory eligibility is isolated from grounded answer generation

The memory decision and persistence workflow SHALL run independently of the grounded answer's evidence policy. It MUST NOT relax, bypass, or alter the query answer's source binding, citation validation, limitation reporting, or safety guardrails.

#### Scenario: User-stated memory conflicts with retrieved evidence

- **WHEN** the user states a durable personal fact that conflicts with a retrieved document and the memory LLM accepts it as user-stated memory
- **THEN** the system MAY persist the user-stated memory, while the current grounded answer continues to report the evidence conflict or limitation according to the existing RAG policy

#### Scenario: Memory decision fails after a successful query

- **WHEN** memory decision or persistence fails after a query has completed
- **THEN** the query result MUST remain successful and the failure MUST NOT change the released grounded answer
