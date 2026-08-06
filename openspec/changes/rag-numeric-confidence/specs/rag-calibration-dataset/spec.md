# rag-calibration-dataset Specification (delta)

## Purpose
Define the versioned labeled calibration fixture dataset that gates numeric confidence
emission. Supports three ingestion paths: operator labeling of answer runs, CSV import,
and synthetic bootstrap generation. Enforces minimum 200 labeled entries before a
calibration model can be trained.

## ADDED Requirements

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

#### Scenario: Operator generates a synthetic bootstrap fixture
- **WHEN** an operator triggers synthetic generation with a count and knowledge base ID
- **THEN** the system samples chunks, generates query-answer pairs via the generation
  provider, assigns programmatic groundedness labels, and persists entries as
  `source = "synthetic_bootstrap"` with version `0.1.0-synthetic`

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
