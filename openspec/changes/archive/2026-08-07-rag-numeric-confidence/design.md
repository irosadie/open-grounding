# Design: rag-numeric-confidence

## Context

`rag-grounded-query` ships a qualitative evidence level (high/medium/low/none) derived
from configured feature thresholds. Numeric confidence was deferred pending a versioned
labeled calibration dataset and a validated abstention threshold. This change satisfies
all three gating conditions: dataset management, calibration model, and threshold
validation — with operator-controlled UI and a safe qualitative fallback when
calibration is incomplete.

## Goals / Non-Goals

**Goals:**

- Add deterministic feature extraction (Stage 1) that runs on every answer, always.
- Add calibration model training (Stage 2, isotonic regression) gated on ≥ 200
  operator-labeled entries per retrieval profile.
- Emit `confidence_score` (0.0–1.0) in answer runs and SSE stream only when a
  validated calibration model is active for the profile.
- Provide `confidence_config` per retrieval profile: feature weights, abstention
  threshold, emit flag, min_labeled_entries, active model ref.
- Provide calibration dataset management: versioned fixtures, CSV import, operator
  labeling UI, and calibration run trigger.
- Provide abstention threshold validation: precision-recall curve computation,
  F1-optimal threshold suggestion, operator review before promotion.
- Console UI at `/console/settings/confidence`: dataset list, labeling workbench,
  calibration run results, threshold configurator, profile promotion.
- Qualitative `evidence_level` remains always present — no behavior regression.

**Non-Goals:**

- Neural or LLM-based confidence models.
- Cross-tenant calibration sharing.
- Automatic re-calibration without operator review.
- Confidence scoring for tool evidence (separate concern).

## Architecture

### New layers

```
Answer Run (existing)
  → ConfidenceFeatureExtractor    (new — Stage 1, always runs, deterministic)
      └→ ConfidenceScorer         (new — Stage 2, runs only if active CalibrationModel)
          └→ IsotonicRegressionModel  (new — sklearn isotonic, versioned per profile)
  → ConfidenceConfig              (new — per-profile config loaded from catalog)
  → answer SSE stream             (extended — confidence_score emitted if calibrated)

Calibration pipeline (async, operator-triggered):
  → CalibrationFixture            (new — versioned labeled dataset per profile)
  → CalibrationRunner             (new — trains isotonic model, computes P-R curve)
  → CalibrationModelVersion       (new — immutable model artifact, stored in object store)
  → ThresholdValidator            (new — suggests F1-optimal threshold, operator confirms)
  → CalibrationPromoter           (new — sets active model ref in confidence_config)
```

### Database schema

```
calibration_fixture
  id                  UUID PK
  tenant_id           UUID FK
  retrieval_profile_id UUID FK
  version             TEXT          -- e.g. "1.0.0", "0.1.0-synthetic"
  source              TEXT          -- "operator_labeled" | "synthetic_bootstrap"
  entry_count         INT
  is_active           BOOLEAN
  created_at          TIMESTAMPTZ
  created_by          UUID          -- operator user id

calibration_fixture_entry
  id                  UUID PK
  fixture_id          UUID FK
  answer_run_id       UUID FK NULL   -- NULL for synthetic/imported entries
  query               TEXT
  evidence_chunk_ids  UUID[]
  answer              TEXT
  confidence_label    TEXT          -- SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED | ABSTAIN
  annotator_id        UUID NULL     -- NULL for CSV import
  annotated_at        TIMESTAMPTZ NULL
  created_at          TIMESTAMPTZ

calibration_model_version
  id                  UUID PK
  tenant_id           UUID FK
  retrieval_profile_id UUID FK
  fixture_id          UUID FK       -- dataset used for training
  artifact_path       TEXT          -- object store path (joblib serialized model)
  feature_names       JSONB         -- ordered list of features used
  threshold_used      FLOAT
  precision_at_threshold FLOAT
  recall_at_threshold    FLOAT
  f1_at_threshold        FLOAT
  entry_count         INT
  is_active           BOOLEAN
  created_at          TIMESTAMPTZ
  promoted_by         UUID NULL     -- operator who promoted

confidence_config
  id                  UUID PK
  tenant_id           UUID FK
  retrieval_profile_id UUID FK UNIQUE
  feature_weights     JSONB         -- per-feature weight overrides, NULL = defaults
  abstention_threshold FLOAT        -- 0.0–1.0, below this → abstain
  emit_numeric_score  BOOLEAN       -- operator opt-in
  min_labeled_entries INT           -- default 200
  active_model_id     UUID FK NULL  -- NULL = not calibrated yet
  updated_at          TIMESTAMPTZ
  updated_by          UUID
```

### Stage 1 — Feature extraction (always runs)

`ConfidenceFeatureExtractor.extract(answer_run) → FeatureVector`

Six features, all derived from existing answer run data:

| Feature | Source | Description |
|---|---|---|
| `reranker_score_mean` | retrieval_summary | mean cross-encoder score of selected evidence |
| `reranker_score_min` | retrieval_summary | min cross-encoder score (weakest chunk) |
| `chunk_coverage_ratio` | validation_outcome | fraction of material claims covered |
| `source_agreement` | selected_evidence | fraction from independent sources |
| `citation_validity_ratio` | validation_outcome | fraction of citations that passed |
| `retrieval_retry_count` | answer_run metadata | 0 or 1 |

Feature weights are configurable via `confidence_config.feature_weights`. Default
weights are equal (1.0 each). The feature vector is persisted with the answer run.

Stage 1 output also drives the existing qualitative classification — no change to
that path.

### Stage 2 — Calibration model (gated)

`ConfidenceScorer.score(feature_vector, profile_id) → float | None`

- Loads `active_model_id` from `confidence_config` for the profile.
- If no active model → returns `None` (qualitative fallback, score omitted).
- If active model exists → loads `IsotonicRegressionModel` from object store cache,
  applies to feature vector, returns calibrated score 0.0–1.0.
- If score < `abstention_threshold` → answer route becomes `abstain` regardless of
  generation output.

Model loading is cached in-process per `calibration_model_version.id`. Cache
invalidated on model promotion.

### Calibration pipeline

Operator-triggered via BullMQ job. The Node worker enqueues the job and calls a
FastAPI internal endpoint to perform the actual training in Python. Pattern follows
the existing ingestion worker convention: worker orchestrates, FastAPI owns all
state mutations and Python-specific computation.

```
POST /confidence/calibrate/{profile_id}  (operator-facing)
  → validate entry_count >= min_labeled_entries → 422 if not
  → enqueue BullMQ job: { tenant_id, profile_id, fixture_id, trace_id }
  → return 202 with job_id

BullMQ Node Worker (CalibrationJobProcessor)
  → receives job
  → POST /internal/confidence/calibrate (FastAPI internal endpoint, not public)
      → CalibrationRunner.run(fixture_id, profile_id, tenant_id):
          1. Load calibration_fixture_entry rows for fixture
          2. Build feature matrix X from persisted feature vectors
          3. Build label vector y: SUPPORTED=1.0, PARTIALLY_SUPPORTED=0.6,
             UNSUPPORTED=0.2, ABSTAIN=0.0
          4. asyncio.get_event_loop().run_in_executor(None, train_isotonic, X, y)
             → IsotonicRegression(increasing=True, out_of_bounds='clip') on 80% split
             → evaluate on 20% held-out split
             → compute P-R curve and F1-optimal threshold
          5. Serialize model to object store (joblib) under calibration/ prefix
          6. Persist calibration_model_version (is_active=False, artifact_path, metrics)
          7. Return model_version_id and P-R curve data to worker
  → worker updates BullMQ job status to completed with result payload

GET /confidence/calibrate/{job_id}/status  (operator polling)
  → return job status, and on complete: model_version_id, P-R curve SVG, f1_optimal_threshold
```

Training runs inside FastAPI via `run_in_executor` (thread pool) to avoid blocking
the event loop. The Node worker only orchestrates the job lifecycle — it never touches
the database or model artifacts directly.

Operator then reviews the curve in the UI, optionally adjusts the threshold, and
promotes the model version via `CalibrationPromoter`.

### CSV import (bootstrap path)

Operators can import a CSV with columns:
`query, answer, confidence_label, evidence_chunk_ids (pipe-separated)`

Imported entries have `annotator_id = NULL`, `source = "operator_labeled"` (operator
takes responsibility on import). CSV import is the bootstrap path for teams without
enough answer run volume yet.

### Hybrid: synthetic bootstrap + real labels

If `entry_count < min_labeled_entries` for real labels, operators can generate a
synthetic bootstrap fixture via the console:

`SyntheticFixtureGenerator.generate(kb_id, count, profile_id)`
- Samples document chunks from the knowledge base
- Generates query-answer pairs using the configured generation provider
- Labels groundedness programmatically: chunk_coverage_ratio > 0.8 → SUPPORTED,
  0.4–0.8 → PARTIALLY_SUPPORTED, < 0.4 → UNSUPPORTED
- Persists as `source = "synthetic_bootstrap"`, version `0.1.0-synthetic`

Synthetic fixtures are valid for initial calibration but must be replaced with
operator-labeled data (`source = "operator_labeled"`) before promotion to production.
`confidence_config.emit_numeric_score` is locked to `false` if active model was trained
on a purely synthetic fixture.

### SSE extension

One new field added to the existing `completed` SSE event:

```json
{
  "event": "completed",
  "data": {
    "evidence_level": "high",
    "confidence_score": 0.87,        ← new, omitted if not calibrated
    "abstention_threshold": 0.35,    ← new, omitted if not calibrated
    "calibration_model_id": "<uuid>" ← new, for traceability
  }
}
```

### Console UI — `/console/settings/confidence`

Four sections in a single page, each a `PanelCard`:

```
1. Calibration Status
   — per-profile: active model version, entry count, last calibrated, emit flag toggle

2. Dataset Management
   — list fixtures (version, source, entry count, status)
   — Upload CSV button → import modal
   — Generate Synthetic button (if entry_count < min_labeled_entries)
   — View Entries button → labeling workbench

3. Labeling Workbench (inline toggle, not separate page)
   — table of answer runs: query preview, answer preview, current label
   — inline label selector: SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED / ABSTAIN
   — Save button per row, bulk save
   — entry count progress bar toward min_labeled_entries

4. Calibration & Threshold
   — Run Calibration button (disabled if entry_count < min_labeled_entries)
   — P-R curve visualization (static SVG from API, not a JS chart lib)
   — F1-optimal threshold suggestion + manual override input
   — Precision / Recall / F1 at current threshold display
   — Promote Model button → inline confirm (Promote + Cancel)
   — Emit Score toggle (locked if model trained on synthetic only)
```

## Decisions

### Isotonic regression, not a neural model

200 labeled entries is sufficient for isotonic regression (monotone, no overfitting)
but insufficient for a neural model. Isotonic runs inline in the API process with no
GPU dependency. Auditable and replaceable.

### Feature weights are configurable, not learned

Operator-tunable weights keep Stage 1 transparent and controllable. A future change
can add learned weights if the dataset grows. Default equal weights are a safe baseline.

### Synthetic bootstrap is valid but locked from production emit

Prevents operators from accidentally shipping uncalibrated scores in production while
still unblocking initial experimentation.

### P-R curve rendered as static SVG from API

No JS chart library dependency. The API computes the curve and returns SVG markup.
Consistent with the existing console's minimal-dependency pattern.

### Calibration runs via BullMQ job → internal FastAPI call

Training even a small isotonic model takes ~1–5 seconds and should not block the
FastAPI request process. The existing Node worker scaffold handles the job lifecycle;
the actual Python training runs in FastAPI via `run_in_executor` (thread pool) when
the worker calls the internal endpoint. This follows the established ingestion pattern:
worker orchestrates, FastAPI owns all Python computation and state mutations.

## Risks / Trade-offs

- [200 entries may be insufficient for multi-feature isotonic regression] → mitigated
  by configurable `min_labeled_entries`; operators can raise it per profile.
- [Feature vector recomputation for old answer runs may be inconsistent] → store
  feature vector alongside answer run at extraction time; never recompute from scratch.
- [Synthetic labels may be systematically biased] → locked from production emit;
  clearly marked as `synthetic_bootstrap` in UI.
- [P-R curve SVG is static, no interactivity] → sufficient for threshold selection;
  interactive chart can be added in a future UI improvement.

## Open Questions

- Should `confidence_score` also be persisted in the `answer_run` table (for
  retrospective analysis), or only emitted via SSE?
- What object store path convention should `calibration_model_version.artifact_path`
  follow — same bucket as document chunks, or a separate `calibration/` prefix?
