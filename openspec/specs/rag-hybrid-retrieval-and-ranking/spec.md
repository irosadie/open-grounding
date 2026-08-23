# rag-hybrid-retrieval-and-ranking Specification

## Purpose
Defines hybrid dense/sparse retrieval with mandatory tenant and ACL filters, RRF-based
fusion, configurable per-index-profile retrieval weights and candidates, diversity
selection, cross-encoder reranking, and qualitative evidence confidence gating.

## Requirements
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

### Requirement: Retrieval configuration is configurable per index profile
The system SHALL provide an optional `RetrievalConfig` attached 1:1 to an `IndexProfile`
containing: `dense_weight` (float, 0.0–5.0, default 1.0), `sparse_weight` (float,
0.0–5.0, default 1.0), `fusion_k` (int, 1–200, default 60), `dense_candidates` (int,
1–200, default 50), `sparse_candidates` (int, 1–200, default 50), `fused_candidates`
(int, 1–200, default 40), `enabled` (bool, default true). If absent, defaults SHALL
be applied. Deleting a `RetrievalConfig` SHALL revert the profile to defaults.

#### Scenario: Sparse weight is set high for a keyword-heavy domain
- **WHEN** an operator sets a high `sparse_weight` for an index profile
- **THEN** the RRF fusion score weights lexical sparse results more heavily than dense
  results, and the fused candidate list reflects that ordering

### Requirement: RetrievalConfig is manageable via API and console UI
The system SHALL expose `GET`, `PUT`, and `DELETE` endpoints at
`/rag/index-profiles/{id}/retrieval` scoped to the tenant and ADMIN-gated for writes.
The index profile settings page SHALL include a "Retrieval" section with fields for
`dense_weight`, `sparse_weight`, `fusion_k`, candidate counts, and an enabled toggle
with inline validation and error display.

#### Scenario: Operator deletes retrieval config
- **WHEN** an operator calls DELETE on the retrieval config for a profile
- **THEN** the config record is removed and subsequent retrievals use default weights
  and candidate counts as if no config existed

