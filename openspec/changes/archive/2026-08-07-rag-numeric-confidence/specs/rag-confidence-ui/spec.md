# rag-confidence-ui Specification (delta)

## Purpose
Provide operators a console UI under `/console/settings/confidence` to manage
calibration datasets, label answer runs, trigger calibration runs, inspect
precision-recall curves, configure thresholds, and promote models — all within the
existing console shell and settings navigation pattern.

## ADDED Requirements

### Requirement: Operators can manage calibration datasets from the console
The system SHALL provide a settings page at `/console/settings/confidence` with a
Dataset Management section listing fixtures per retrieval profile (version, source,
entry count, active status). Operators SHALL be able to upload a CSV, generate a
synthetic bootstrap fixture, and view entries. The page MUST follow the existing
`PanelCard` + inline form pattern.

#### Scenario: Operator uploads a CSV fixture
- **WHEN** an operator selects a CSV file and submits the import form
- **THEN** the system validates the CSV server-side, returns inline errors for invalid
  rows, and on success refreshes the fixture list showing the new entry count

#### Scenario: Operator generates a synthetic bootstrap fixture
- **WHEN** an operator clicks Generate Synthetic and selects a knowledge base and count
- **THEN** a BullMQ job is enqueued, the UI shows a pending state, and on completion
  the fixture appears in the list marked as `synthetic_bootstrap`

### Requirement: Operators can label answer runs in the console labeling workbench
The system SHALL provide an inline labeling workbench (toggled within the page, not a
separate route) showing unlabeled answer runs for the selected profile. Each row shows
query preview (first 120 chars), answer preview (first 120 chars), and a label
selector. A progress bar shows current labeled count vs `min_labeled_entries`. Bulk
save MUST be supported.

#### Scenario: Operator labels multiple answer runs and bulk saves
- **WHEN** an operator assigns labels to multiple rows and clicks Save All
- **THEN** all labeled entries are persisted in one request, the progress bar updates,
  and rows that were saved are visually confirmed

#### Scenario: Entry count reaches min_labeled_entries
- **WHEN** the labeled entry count equals or exceeds `min_labeled_entries`
- **THEN** the progress bar shows complete state and the Run Calibration button
  becomes enabled

### Requirement: Operators can run calibration and inspect results from the console
The system SHALL provide a Calibration & Threshold section with a Run Calibration
button (disabled below `min_labeled_entries`), a polling status indicator while the
job runs, and a results panel showing the P-R curve as a static SVG, F1-optimal
threshold suggestion, precision/recall/F1 at current threshold, and a manual threshold
override input.

#### Scenario: Calibration job completes and results are displayed
- **WHEN** a calibration BullMQ job completes
- **THEN** the UI displays the P-R curve SVG returned by the API, the F1-optimal
  threshold pre-filled in the threshold input, and enables the Promote Model button

#### Scenario: Operator overrides the threshold before promoting
- **WHEN** an operator changes the threshold input value
- **THEN** the precision, recall, and F1 fields update to reflect the new threshold
  value before the operator confirms promotion

### Requirement: Operators can configure confidence settings per profile from the console
The system SHALL provide a Calibration Status section showing per-profile: active model
version, entry count, last calibrated timestamp, emit score toggle, abstention threshold
input, min_labeled_entries input, and feature weight overrides. All fields are
editable inline and saved via PATCH. The emit score toggle MUST be visually disabled
(not just validation-blocked) when no active calibration model exists.

#### Scenario: Operator attempts to enable emit score without active model
- **WHEN** an operator tries to toggle emit_numeric_score on for a profile with no
  active model
- **THEN** the toggle is rendered as disabled with a tooltip explaining that a promoted
  calibration model is required

### Requirement: Confidence UI follows existing console patterns exactly
The system SHALL implement the confidence settings page using the same conventions as
`models-content.tsx` and `index-profiles-content.tsx`: `"use client"` content
component, `PanelCard` containers, inline toggled forms, Zod `safeParse` validation,
`useMutation` with `onSuccess` invalidation, native `<select>` for enum fields, no
react-hook-form, no external chart library (P-R curve is a static SVG from API).

#### Scenario: Confidence page loads within console layout
- **WHEN** an operator navigates to `/console/settings/confidence`
- **THEN** the page renders within the console sidebar layout with the Confidence nav
  item highlighted as active, and the Calibration Status section loads profile data
