## ADDED Requirements

### Requirement: Query scope and policy are server-derived
The system SHALL accept a query message, optional conversation ID, authorized
knowledge-base selection, safe metadata filters, mode, and stream preference. It MUST
derive tenant, ACL principals, classification clearance, active generations, and
effective-time policy from authenticated server context and MUST ignore client attempts
to provide or override those values.

#### Scenario: Client attempts to override tenant or ACL scope
- **WHEN** a query request includes a tenant, ACL, clearance, or vector-filter value
- **THEN** the server ignores the untrusted value and accesses evidence only through
  the authenticated tenant and policy context

### Requirement: Query admission and route selection are bounded
The system SHALL enforce configured rate, token, payload, concurrency, knowledge-base,
and policy checks before retrieval. It MUST route a request only to `grounded`,
`clarify`, or `abstain` in the initial release and MUST bound query rewriting to at
most one attempted retry.

#### Scenario: Query lacks an authorized evidence path
- **WHEN** a query has no authorized knowledge base or violates configured policy
- **THEN** the system returns a clarification or abstention outcome without invoking
  retrieval or generation

### Requirement: Conversation preprocessing preserves user intent
The system SHALL retain the original message and record any normalized or standalone
query as derived trace data. It MAY use a bounded recent conversation window but MUST
NOT add retrieved source content to long-term memory in this release.

#### Scenario: Query is normalized for retrieval
- **WHEN** the query normalizer creates a standalone form from recent conversation
- **THEN** the original query remains part of retrieval/trace context and the derived
  form cannot change tenant or authorization scope
