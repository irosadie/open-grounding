# rag-numeric-confidence Specification

## Purpose
Defines the numeric confidence pipeline: deterministic feature extraction per answer
run, operator-managed calibration fixture datasets, isotonic regression calibration
model training and promotion, per-profile confidence configuration, abstention
threshold enforcement, and the operator console UI for dataset management, labeling,
calibration, and threshold configuration.

## Requirements

### Requirement: Numeric confidence is calibrated against labeled data
The system SHALL emit a calibrated numeric confidence score with each answer only after
a versioned labeled calibration dataset calibrates the score and an abstention threshold
is validated against it. It MUST NOT treat a raw vector similarity score as confidence
and MUST NOT expose a numeric confidence value before calibration is complete.

#### Scenario: Calibration dataset does not yet exist
- **WHEN** no versioned labeled calibration dataset is available for a profile
- **THEN** the system returns the qualitative evidence level (high/medium/low/none)
  and omits any numeric confidence value

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

### Requirement: Calibration fixtures are versioned and tenant-scoped
The system SHALL store calibration fixtures in a `calibration_fixture` table scoped
to a tenant and retrieval profile with a version string, source type, entry count, and
active flag. Only one fixture may be active per (tenant_id, retrieval_profile_id) at
a time.

#### Scenario: Operator activates a new fixture version
- **WHEN** an operator promotes a fixture to active for a profile
- **THEN** the previous active fixture is deactivated and the new fixture becomes
  the source for any subsequent calibration run

### Requirement: Operators label answer runs directly in the console
The system SHALL allow operators to assign a `confidence_label` to any answer run
that has a persisted feature vector. Labels MUST be one of: SUPPORTED,
PARTIALLY_SUPPORTED, UNSUPPORTED, ABSTAIN. The labeling workbench MUST show query
preview, answer preview, current label, and a progress bar toward `min_labeled_entries`.

#### Scenario: Operator labels an answer run
- **WHEN** an operator selects a label for an answer run in the labeling workbench
- **THEN** a `calibration_fixture_entry` row is created or updated with the label,
  annotator_id, and annotated_at timestamp, and the fixture entry_count is incremented

### Requirement: Operators can import labels via CSV
The system SHALL accept a CSV file with columns: `query`, `answer`,
`confidence_label`, `evidence_chunk_ids` (pipe-separated UUIDs). Imported entries
are stored with `annotator_id = NULL` and `source = "operator_labeled"`. The system
MUST validate that `confidence_label` values are within the allowed enum and that
`evidence_chunk_ids` reference chunks belonging to the tenant before persisting.

#### Scenario: CSV contains an invalid confidence_label
- **WHEN** an operator uploads a CSV with a row containing an unrecognized label value
- **THEN** the system rejects the entire import with a validation error listing the
  invalid rows; no entries are persisted

### Requirement: Synthetic bootstrap fixtures are generatable but locked from production emit
The system SHALL support generating a synthetic fixture via `SyntheticFixtureGenerator`
when real labeled entry count is below `min_labeled_entries`. Synthetic fixtures are
stored with `source = "synthetic_bootstrap"`. A calibration model trained exclusively
on a synthetic fixture MUST NOT enable `emit_numeric_score` in `confidence_config`.

#### Scenario: Operator attempts to emit numeric score from a synthetic-only model
- **WHEN** an operator tries to enable `emit_numeric_score` for a profile whose
  active model was trained on a synthetic fixture
- **THEN** the system rejects the toggle and returns a validation error indicating that
  operator-labeled data is required before production emission

### Requirement: Calibration cannot start below minimum labeled entry threshold
The system SHALL prevent triggering a calibration run if the active fixture has fewer
than `confidence_config.min_labeled_entries` entries with `source = "operator_labeled"`.
The default minimum is 200 and is configurable per tenant profile.

#### Scenario: Operator triggers calibration with insufficient labels
- **WHEN** an operator clicks Run Calibration and the operator-labeled entry count
  is below `min_labeled_entries`
- **THEN** the system returns a validation error with the current count and the
  required minimum; no calibration job is enqueued

### Requirement: Calibration training is triggered via BullMQ job and executed in FastAPI
The system SHALL enqueue a BullMQ job when an operator triggers a calibration run.
The Node worker SHALL call a FastAPI internal endpoint to perform the actual isotonic
regression training in Python. The FastAPI public endpoint MUST NOT perform training
inline — it enqueues the job and returns 202 immediately.

#### Scenario: Operator triggers a calibration run
- **WHEN** an operator calls the calibration run endpoint for a valid fixture
- **THEN** the system validates entry count, enqueues a BullMQ job, and returns 202
  with a job_id; the Node worker calls the FastAPI internal endpoint which runs
  training and persists the result; the operator polls for completion status

### Requirement: Calibration model is isotonic regression trained on labeled fixtures
The system SHALL train an `IsotonicRegression(increasing=True, out_of_bounds="clip")`
model on the feature matrix derived from the active fixture (80/20 train/eval split).
Label encoding: SUPPORTED=1.0, PARTIALLY_SUPPORTED=0.6, UNSUPPORTED=0.2, ABSTAIN=0.0.

#### Scenario: Calibration completes successfully
- **WHEN** a calibration job finishes with sufficient entries and no training error
- **THEN** a `calibration_model_version` record is persisted with `is_active=False`,
  artifact_path in object store, f1_at_threshold, precision_at_threshold,
  recall_at_threshold, and the F1-optimal threshold suggestion

### Requirement: Model promotion is operator-confirmed and recorded
The system SHALL require an explicit operator confirmation to promote a calibration
model version to active. Promotion sets `is_active=True` on the new version,
`is_active=False` on the previous, updates `confidence_config.active_model_id`,
and records `promoted_by` and timestamp.

#### Scenario: Operator promotes a calibration model
- **WHEN** an operator confirms promotion of a model version
- **THEN** the active model reference in confidence_config is updated atomically,
  the in-process model cache is invalidated, and subsequent answer runs use the new model

### Requirement: Confidence configuration is stored per retrieval profile
The system SHALL maintain a `confidence_config` record for every retrieval profile.
A profile with no confidence_config record SHALL behave as if `emit_numeric_score=false`
and `active_model_id=NULL` — qualitative evidence level only, no numeric score emitted.

#### Scenario: Profile has no confidence_config
- **WHEN** an answer run completes for a profile with no confidence_config record
- **THEN** the system emits `evidence_level` only; `confidence_score` is omitted

### Requirement: emit_numeric_score is operator opt-in per profile
The system SHALL default `emit_numeric_score=false` for all profiles. The system MUST
reject enabling `emit_numeric_score` if `active_model_id` is NULL or if the active
model was trained on a synthetic-only fixture.

#### Scenario: Operator enables emit_numeric_score without an active model
- **WHEN** an operator sets `emit_numeric_score=true` for a profile with no active
  calibration model
- **THEN** the system returns 422 and does not update the config

### Requirement: abstention_threshold overrides query route when score is below threshold
The system SHALL store `abstention_threshold` as a float in [0.0, 1.0]. When
`emit_numeric_score=true` and a calibrated score is below `abstention_threshold`,
the query route MUST be overridden to `abstain` before generation.

#### Scenario: Calibrated score falls below abstention threshold
- **WHEN** `ConfidenceScorer` returns a score below `confidence_config.abstention_threshold`
- **THEN** the query planner overrides the route to `abstain` and no generated answer
  is produced

### Requirement: Operators can manage calibration datasets from the console
The system SHALL provide a settings page at `/console/settings/confidence` with Dataset
Management, Labeling Workbench, Calibration & Threshold, and Calibration Status sections.
The page MUST follow the existing `PanelCard` + inline form pattern used by the console.

#### Scenario: Operator uploads a CSV fixture
- **WHEN** an operator selects a CSV file and submits the import form
- **THEN** the system validates the CSV server-side, returns inline errors for invalid
  rows, and on success refreshes the fixture list showing the new entry count

#### Scenario: Calibration job completes and results are displayed
- **WHEN** a calibration BullMQ job completes
- **THEN** the UI displays the P-R curve SVG returned by the API, the F1-optimal
  threshold pre-filled in the threshold input, and enables the Promote Model button
