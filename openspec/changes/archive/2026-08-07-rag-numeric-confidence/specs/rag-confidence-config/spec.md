# rag-confidence-config Specification (delta)

## Purpose
Define the per-retrieval-profile confidence configuration that controls feature
weights, abstention threshold, emit flag, minimum labeled entry requirement, and
active calibration model reference. All fields are operator-configurable and stored
in the catalog.

## ADDED Requirements

### Requirement: Confidence configuration is stored per retrieval profile
The system SHALL maintain a `confidence_config` record for every retrieval profile.
A profile with no confidence_config record SHALL behave as if `emit_numeric_score=false`
and `active_model_id=NULL` — qualitative evidence level only, no numeric score emitted.

#### Scenario: Profile has no confidence_config
- **WHEN** an answer run completes for a profile with no confidence_config record
- **THEN** the system emits `evidence_level` only; `confidence_score` is omitted
  from the answer run and SSE stream

### Requirement: emit_numeric_score is operator opt-in per profile
The system SHALL default `emit_numeric_score=false` for all profiles. An operator
MUST explicitly enable it. The system MUST reject enabling `emit_numeric_score` if
`active_model_id` is NULL or if the active model was trained on a synthetic-only fixture.

#### Scenario: Operator enables emit_numeric_score without an active model
- **WHEN** an operator sets `emit_numeric_score=true` for a profile with no active
  calibration model
- **THEN** the system returns 422 and does not update the config

### Requirement: abstention_threshold is configurable and range-validated
The system SHALL store `abstention_threshold` as a float in [0.0, 1.0] in
`confidence_config`. When `emit_numeric_score=true` and a calibrated score is below
`abstention_threshold`, the query route MUST be overridden to `abstain` before
generation. Changing the threshold takes effect on subsequent queries without
requiring a new calibration run.

#### Scenario: Calibrated score falls below abstention threshold
- **WHEN** `ConfidenceScorer` returns a score below `confidence_config.abstention_threshold`
- **THEN** the query planner overrides the route to `abstain` and no generated answer
  is produced

### Requirement: min_labeled_entries is configurable per profile
The system SHALL use `confidence_config.min_labeled_entries` (default 200) as the hard
floor for operator-labeled entries required before a calibration run is permitted.
Operators MAY increase but SHOULD NOT decrease this value below 100 without explicit
confirmation. The system MUST warn (but not block) if an operator sets a value below 100.

#### Scenario: Operator sets min_labeled_entries below 100
- **WHEN** an operator updates `min_labeled_entries` to a value less than 100
- **THEN** the system saves the value but returns a warning in the response body
  indicating that accuracy may be degraded below 100 entries

### Requirement: feature_weights updates take effect immediately without re-training
The system SHALL apply updated `feature_weights` from `confidence_config` to all
subsequent answer runs without requiring a calibration run. The active calibration
model artifact is unchanged; only the Stage 1 weighted feature vector computation
is affected.

#### Scenario: Operator updates feature weights
- **WHEN** an operator PATCHes `feature_weights` in confidence_config
- **THEN** the next answer run uses the updated weights for qualitative classification;
  the active calibration model and its threshold are unchanged
