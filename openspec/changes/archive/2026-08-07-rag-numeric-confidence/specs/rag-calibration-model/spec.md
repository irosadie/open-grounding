# rag-calibration-model Specification (delta)

## Purpose
Define the calibration model training pipeline, versioned model artifact storage,
abstention threshold validation, and operator-controlled promotion to active. A model
is immutable once created; promotion replaces the active model reference in
confidence_config.

## ADDED Requirements

### Requirement: Calibration training is triggered via BullMQ job and executed in FastAPI
The system SHALL enqueue a BullMQ job when an operator triggers a calibration run.
The Node worker SHALL call a FastAPI internal endpoint to perform the actual isotonic
regression training in Python. The FastAPI public endpoint MUST NOT perform training
inline — it enqueues the job and returns 202 immediately. The Node worker MUST NOT
write to the database or object store directly; all state mutations occur inside the
FastAPI internal endpoint.

#### Scenario: Operator triggers a calibration run
- **WHEN** an operator calls the calibration run endpoint for a valid fixture
- **THEN** the system validates entry count, enqueues a BullMQ job, and returns 202
  with a job_id; the Node worker calls the FastAPI internal endpoint which runs
  training and persists the result; the operator polls for completion status

### Requirement: Calibration model is isotonic regression trained on labeled fixtures
The system SHALL train an `IsotonicRegression(increasing=True, out_of_bounds="clip")`
model from scikit-learn on the feature matrix and label vector derived from the active
fixture. Label encoding: SUPPORTED=1.0, PARTIALLY_SUPPORTED=0.6, UNSUPPORTED=0.2,
ABSTAIN=0.0. The model SHALL be trained on 80% of entries and evaluated on a held-out
20% split. Training MUST be reproducible given the same fixture version.

#### Scenario: Calibration completes successfully
- **WHEN** a calibration job finishes with sufficient entries and no training error
- **THEN** a `calibration_model_version` record is persisted with `is_active=False`,
  artifact_path in object store, f1_at_threshold, precision_at_threshold,
  recall_at_threshold, and the F1-optimal threshold suggestion

### Requirement: Calibration model artifact is stored in object store and cached in process
The system SHALL serialize the trained model via joblib and write it to the object
store under a `calibration/` prefix path. On first use per model version, the API
process loads and caches the artifact in memory. The cache is invalidated when a new
model version is promoted to active.

#### Scenario: API process loads a promoted model on first query
- **WHEN** a query runs against a profile with a newly promoted calibration model
- **THEN** the process loads the artifact from object store, caches it by
  model_version_id, and uses it for all subsequent queries without re-fetching

### Requirement: Abstention threshold is validated before promotion
The system SHALL compute a precision-recall curve on the held-out evaluation split and
suggest the F1-optimal threshold. The operator MAY override the threshold within
0.0–1.0. The system MUST record the final precision, recall, and F1 at the chosen
threshold in the `calibration_model_version` record before promotion is allowed.

#### Scenario: Operator overrides the suggested threshold
- **WHEN** an operator enters a custom threshold and clicks Promote
- **THEN** the system recomputes precision, recall, and F1 at the custom threshold,
  updates the model version record, and proceeds with promotion if operator confirms

### Requirement: Model promotion is operator-confirmed and recorded
The system SHALL require an explicit operator confirmation action to promote a
calibration model version to active. Promotion sets `is_active=True` on the new
version, `is_active=False` on the previous version, updates
`confidence_config.active_model_id`, and records `promoted_by` and timestamp.
Promotion is irreversible via UI; a previous version can be re-promoted by a new run.

#### Scenario: Operator promotes a calibration model
- **WHEN** an operator confirms promotion of a model version
- **THEN** the active model reference in confidence_config is updated atomically,
  the in-process model cache is invalidated, and subsequent answer runs use the new model
