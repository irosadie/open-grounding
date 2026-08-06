# rag-numeric-confidence Specification

## Purpose
TBD - created by archiving change rag-query-deferred-followups. Update Purpose after archive.
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
