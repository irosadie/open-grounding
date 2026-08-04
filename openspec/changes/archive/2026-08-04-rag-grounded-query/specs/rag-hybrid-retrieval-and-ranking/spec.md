## ADDED Requirements

### Requirement: Dense and sparse retrieval share mandatory filters
The system SHALL execute dense and sparse Qdrant retrieval with the same server-built
tenant, knowledge-base, active generation/version, classification, ACL, effective-time,
and caller-safe metadata filters. Policy filtering MUST occur in the retrieval adapter,
not after candidates are returned.

#### Scenario: Query searches a restricted knowledge base
- **WHEN** an authorized query is executed against a knowledge base with ACL and
  classification constraints
- **THEN** dense and sparse candidate lists contain only permitted active chunks before
  fusion or reranking

### Requirement: Hybrid candidates are fused and diversified deterministically
The system SHALL fuse dense and sparse candidate ranks using RRF, then remove exact or
near duplicates, superseded content, and excessive same-source dominance before
reranking. Candidate budgets MUST come from a versioned retrieval profile.

#### Scenario: Dense and sparse results overlap
- **WHEN** dense and sparse retrieval return overlapping chunks and one document
  dominates the candidate set
- **THEN** RRF, deduplication, and diversity selection produce a bounded candidate set
  with stable source identities for reranking

### Requirement: Reranking does not override access policy
The system SHALL rerank only pre-filtered candidates using a versioned cross-encoder
profile with bounded input, batching, timeout, and deterministic fallback behavior.

#### Scenario: Reranker times out
- **WHEN** the configured reranker exceeds its timeout or is unavailable
- **THEN** the system follows the configured fallback and records the degradation
  without adding unfiltered candidates or bypassing the confidence gate

### Requirement: Evidence confidence is not a raw similarity score
The system SHALL use configured evidence features to produce high, medium, low, or no
evidence outcomes. It MUST NOT expose a numeric confidence score until a labeled,
versioned calibration dataset is active.

#### Scenario: Retrieval returns weak evidence
- **WHEN** reranked candidates have insufficient quality, agreement, coverage, or
  independent support
- **THEN** the system performs at most one bounded retry, asks for clarification, or
  abstains rather than generating a confident factual answer
