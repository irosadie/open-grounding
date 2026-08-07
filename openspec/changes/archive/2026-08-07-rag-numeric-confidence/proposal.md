# Proposal: rag-numeric-confidence

## Problem

The current RAG pipeline emits a qualitative evidence level (high / medium / low / none)
derived from configured thresholds. This is correct and safe for the initial release, but
it limits operator observability: there is no way to know *how* high or low the
confidence is within a band, and abstention thresholds are tuned by intuition rather than
measured against real query outcomes.

Exposing a raw vector similarity score as confidence would be misleading — similarity
is a retrieval proxy, not a calibrated probability. The deferred spec explicitly prohibits
this. What is needed is a score that is:

1. Calibrated against real labeled outcomes from this tenant's domain.
2. Validated against an abstention threshold before being emitted.
3. Not exposed until calibration is complete (qualitative fallback in the interim).

## Proposed Solution

Add a **Numeric Confidence** capability that:

- Uses a **hybrid scoring approach**: combines evidence features (reranker score, chunk
  coverage, source agreement, citation validity) with a lightweight calibrated isotonic
  regression model trained on labeled calibration fixtures.
- Emits a `confidence_score` (0.0–1.0) and `abstention_threshold` alongside the
  existing qualitative `evidence_level` — both are configurable per retrieval profile.
- Gated by a **versioned labeled calibration dataset** of at minimum 200 operator-labeled
  entries per retrieval profile before the score is emitted.
- Provides a **console UI** under `/console/settings/confidence` for operators to:
  - Upload or build a calibration fixture dataset.
  - Label answer runs (SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED / ABSTAIN).
  - Trigger calibration runs and inspect precision-recall curves.
  - Set and validate the abstention threshold.
  - Promote a calibrated profile to active.

## Hybrid Approach

The score is computed in two stages:

**Stage 1 — Feature extraction (deterministic, always runs):**
Combine evidence features into a feature vector per answer run:
- `reranker_score_mean` — mean cross-encoder score of selected evidence
- `reranker_score_min` — min cross-encoder score (weakest evidence)
- `chunk_coverage_ratio` — fraction of material claims covered by evidence
- `source_agreement` — fraction of evidence chunks from independent sources
- `citation_validity_ratio` — fraction of citations validated by the answer validator
- `retrieval_retry_count` — 0 or 1 (retry signals weak initial retrieval)

**Stage 2 — Calibration model (requires labeled dataset):**
Isotonic regression trained on labeled fixtures maps the feature vector → calibrated
probability. Isotonic regression is chosen because:
- Monotonicity is a natural constraint (higher feature scores → higher confidence).
- It does not overfit on small datasets (200 entries is sufficient).
- It is interpretable and auditable — operators can inspect the mapping.
- No GPU or external model required — runs inline in the API process.

Before calibration is complete, Stage 1 features are used only for the existing
qualitative classification. Stage 2 is skipped and `confidence_score` is omitted.

## Configurability

All thresholds and weights are configurable per retrieval profile via the catalog:

```
confidence_config
  retrieval_profile_id    UUID FK
  feature_weights         JSONB    ← per-feature weight overrides
  abstention_threshold    FLOAT    ← below this score → abstain
  emit_numeric_score      BOOLEAN  ← operator opt-in per profile
  min_labeled_entries     INT      ← default 200, configurable per tenant
  calibration_model_ref   UUID FK  ← active calibration model version
```

## Scope

**In scope:**
- Feature extraction pipeline (Stage 1) — deterministic, no model required.
- Calibration dataset management: versioned fixtures, operator labeling, CSV import.
- Calibration model training: isotonic regression, versioned per retrieval profile.
- Abstention threshold validation: precision-recall curve, F1-optimal threshold suggestion.
- `confidence_score` emission in answer runs and SSE stream once calibrated.
- Configurable `confidence_config` per retrieval profile.
- Console UI: `/console/settings/confidence` — dataset management, labeling, calibration,
  threshold configuration, profile promotion.
- Qualitative fallback when calibration is incomplete — no behavior regression.

**Out of scope:**
- Neural confidence models (BERT-based, LLM-based confidence heads).
- Cross-tenant calibration sharing.
- Automatic re-calibration without operator review.
- Confidence scoring for tool evidence (separate concern, deferred).

## Gating Conditions Met

From `rag-numeric-confidence` deferred spec:
1. Versioned labeled calibration dataset — met by `calibration_fixture` table with
   version, `retrieval_profile_id`, and operator-labeled entries.
2. Abstention threshold validated against dataset — met by threshold validation step
   using precision-recall curve before promotion.
3. Minimum 200 labeled entries — configurable via `min_labeled_entries`, default 200.

## Non-Goals

- Replace the qualitative `evidence_level` — it remains always present.
- Emit `confidence_score` without a validated calibration model active.
- Allow tenants to share or copy calibration models across profiles.
- Auto-promote a calibration model without operator review.
