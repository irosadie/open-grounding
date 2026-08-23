# rag-confidence-feature-extraction Specification (delta)

## Purpose
Define the deterministic Stage 1 feature extraction pipeline that runs on every answer
run regardless of calibration status. Feature vectors are the shared input to both the
existing qualitative evidence classification and the calibrated numeric scorer.

## ADDED Requirements

### Requirement: Feature vector is extracted and persisted for every answer run
The system SHALL compute a six-feature vector for every completed answer run and
persist it alongside the answer run record. Feature extraction MUST be deterministic
given the same answer run inputs and MUST NOT depend on a calibration model.

Features:
- `reranker_score_mean` — mean cross-encoder score of selected evidence chunks
- `reranker_score_min` — minimum cross-encoder score across selected evidence
- `chunk_coverage_ratio` — fraction of material claims covered by selected evidence
- `source_agreement` — fraction of evidence chunks from independent source documents
- `citation_validity_ratio` — fraction of citations that passed answer validation
- `retrieval_retry_count` — 0 or 1 (whether retrieval was retried for this run)

#### Scenario: Answer run completes with selected evidence
- **WHEN** the answer validation pipeline completes for a query
- **THEN** `ConfidenceFeatureExtractor` computes all six features from the answer run
  data and persists the feature vector with the answer run before SSE completion is emitted

#### Scenario: Answer run abstains or returns clarification
- **WHEN** the answer route is `abstain` or `clarify`
- **THEN** the feature vector is still computed and persisted with partial values where
  applicable; features unavailable for the route are set to 0.0

### Requirement: Feature weights are configurable per retrieval profile
The system SHALL apply per-feature weights from `confidence_config.feature_weights`
when combining features into a weighted feature vector for qualitative classification.
If no weights are configured for a profile, equal weights of 1.0 per feature SHALL be
used. Weight changes MUST NOT require re-training the calibration model.

#### Scenario: Operator updates feature weights for a profile
- **WHEN** an operator updates `feature_weights` in `confidence_config` for a profile
- **THEN** subsequent answer runs use the new weights for qualitative classification
  without requiring a calibration run; the existing active calibration model is unchanged

### Requirement: Feature vector is never recomputed from scratch after persistence
The system SHALL use the persisted feature vector when building calibration fixtures
from historical answer runs. It MUST NOT recompute features from raw retrieval data
retroactively, as retrieval profiles or reranker models may have changed since the run.

#### Scenario: Operator builds a calibration fixture from historical answer runs
- **WHEN** the calibration pipeline loads answer runs for fixture construction
- **THEN** it reads the persisted feature vector from each answer run record rather
  than recomputing from retrieval data
