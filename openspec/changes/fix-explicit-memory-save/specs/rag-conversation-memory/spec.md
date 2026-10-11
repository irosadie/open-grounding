## MODIFIED Requirements

### Requirement: Long-term memory is retention-aware and opt-in

The system SHALL persist bounded, durable user preferences, user-stated facts, or other
future-useful user context as long-term memory only under a documented retention and
redaction policy and explicit tenant opt-in. A memory-capable LLM SHALL evaluate each
eligible completed conversation and return an explicit decision indicating whether a
memory should be stored, together with a non-empty summary when the decision is
positive. The system MUST NOT write a memory chunk when the decision is negative, the
summary is empty, or the content is only a transient question, assistant-generated
claim, retrieved source fact, secret, or other content excluded by the memory policy.
An explicit user request to remember, save, or store durable personal context SHALL make
the conversation eligible for evaluation even when it has fewer turns than the normal
configured minimum. Ordinary short conversations SHALL continue to respect that
minimum. The system MUST NOT enable autonomous background agents in this release.

#### Scenario: Explicit save request is evaluated immediately

- **WHEN** memory is opted in and a USER message explicitly asks to remember, save, or
  store a durable personal fact or preference
- **AND** the completed conversation has fewer turns than the configured minimum
- **THEN** the system evaluates the conversation with the memory LLM and may persist a
  bounded summary if the decision is positive

#### Scenario: Ordinary short conversation still respects the threshold

- **WHEN** memory is opted in and a completed conversation has fewer turns than the
  configured minimum without an explicit memory request
- **THEN** the system does not call the memory LLM or create a memory chunk

#### Scenario: Explicit save request does not bypass policy filters

- **WHEN** a user explicitly asks to save a secret, unsupported assumption, transient
  question, or source-only fact
- **THEN** the memory LLM policy still rejects the content and no memory chunk is
  created

#### Scenario: Concrete explicit fact is not replaced by a consent summary

- **WHEN** the memory LLM accepts an explicit save request that contains a high-
  confidence concrete name or preference
- **THEN** the persisted summary represents the concrete user fact or preference rather
  than a generic statement that the user permitted memory storage

#### Scenario: Generic model rejection does not discard a high-confidence explicit fact

- **WHEN** a high-confidence explicit name or preference is present and the memory LLM
  returns only a generic consent/permission rejection
- **THEN** the system persists the normalized concrete fact, while safety, source-only,
  unsupported, and transient rejection reasons continue to block persistence

#### Scenario: Memory write is not opt-in for the tenant

- **WHEN** a memory write is attempted and the tenant has not explicitly opted in
- **THEN** the system discards the memory write and continues the query without
  persisting any long-term memory

#### Scenario: Memory LLM rejects a conversation as not memory-worthy

- **WHEN** the memory LLM returns a negative store decision or an empty summary
- **THEN** the system MUST NOT create a memory chunk for that conversation

#### Scenario: Memory LLM accepts a durable user-stated fact

- **WHEN** an opted-in completed conversation contains a durable fact or preference
  explicitly stated by the user and the memory LLM returns a positive store decision
  with a summary
- **THEN** the system persists the bounded summary subject to the configured retention
  and embedding policy

#### Scenario: Retrieved source content is not treated as user memory

- **WHEN** a conversation contains a fact only because it appears in retrieved
  knowledge-base evidence and the user does not state or adopt it as their own durable
  context
- **THEN** the system MUST NOT persist that source-only fact as long-term user memory
