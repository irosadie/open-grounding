# Tasks: rag-numeric-confidence

## 1. Database schema

- [ ] 1.1 Write SQLAlchemy ORM model for `calibration_fixture` (id, tenant_id, retrieval_profile_id, version, source enum, entry_count, is_active, created_at, created_by).
- [ ] 1.2 Write SQLAlchemy ORM model for `calibration_fixture_entry` (id, fixture_id, answer_run_id nullable, query, evidence_chunk_ids UUID[], answer, confidence_label, annotator_id nullable, annotated_at nullable, created_at).
- [ ] 1.3 Write SQLAlchemy ORM model for `calibration_model_version` (id, tenant_id, retrieval_profile_id, fixture_id, artifact_path, feature_names JSONB, threshold_used, precision_at_threshold, recall_at_threshold, f1_at_threshold, entry_count, is_active, created_at, promoted_by nullable).
- [ ] 1.4 Write SQLAlchemy ORM model for `confidence_config` (id, tenant_id, retrieval_profile_id UNIQUE, feature_weights JSONB nullable, abstention_threshold, emit_numeric_score, min_labeled_entries default 200, active_model_id nullable FK, updated_at, updated_by).
- [ ] 1.5 Add `feature_vector` JSONB column to existing `answer_run` table via Alembic migration.
- [ ] 1.6 Generate Alembic migration for the four new tables; verify applies cleanly on fresh DB.
- [ ] 1.7 Add partial unique index on `calibration_fixture(tenant_id, retrieval_profile_id)` where `is_active = true`.
- [ ] 1.8 Add partial unique index on `calibration_model_version(tenant_id, retrieval_profile_id)` where `is_active = true`.

## 2. Domain layer

- [ ] 2.1 Add `CalibrationFixture` domain entity with version, source, entry_count, is_active.
- [ ] 2.2 Add `CalibrationFixtureEntry` domain entity with confidence_label, annotator_id, annotated_at.
- [ ] 2.3 Add `CalibrationModelVersion` domain entity with artifact_path, feature_names, threshold metrics, is_active.
- [ ] 2.4 Add `ConfidenceConfig` domain entity with feature_weights, abstention_threshold, emit_numeric_score, min_labeled_entries, active_model_id.
- [ ] 2.5 Add `ConfidenceLabel` enum to `packages/schemas/`: SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, ABSTAIN.
- [ ] 2.6 Add `CalibrationSource` enum to `packages/schemas/`: OPERATOR_LABELED, SYNTHETIC_BOOTSTRAP.
- [ ] 2.7 Define `ICalibrationFixtureRepository` protocol: `save`, `get_active(tenant_id, profile_id)`, `list(tenant_id, profile_id)`, `deactivate_previous`, `append_entries`, `count_labeled_entries`.
- [ ] 2.8 Define `ICalibrationModelRepository` protocol: `save`, `get_active(tenant_id, profile_id)`, `promote(model_id, promoted_by)`, `list(tenant_id, profile_id)`.
- [ ] 2.9 Define `IConfidenceConfigRepository` protocol: `get_or_default(tenant_id, profile_id)`, `upsert`, `set_active_model`.

## 3. Infrastructure layer

- [ ] 3.1 Implement `SqlCalibrationFixtureRepository` (async SQLAlchemy) for `ICalibrationFixtureRepository`; enforce tenant scope on all reads/writes.
- [ ] 3.2 Implement `SqlCalibrationModelRepository` (async SQLAlchemy) for `ICalibrationModelRepository`; enforce tenant scope.
- [ ] 3.3 Implement `SqlConfidenceConfigRepository` (async SQLAlchemy) for `IConfidenceConfigRepository`; `get_or_default` returns config with all defaults if no record exists.
- [ ] 3.4 Extend existing `SqlAnswerRunRepository` to persist and read `feature_vector` JSONB column.

## 4. Application layer — feature extraction

- [ ] 4.1 Implement `ConfidenceFeatureExtractor.extract(answer_run) → FeatureVector`: compute all six features (reranker_score_mean, reranker_score_min, chunk_coverage_ratio, source_agreement, citation_validity_ratio, retrieval_retry_count).
- [ ] 4.2 Apply `confidence_config.feature_weights` to produce weighted feature vector; fall back to equal weights if no config.
- [ ] 4.3 Wire `ConfidenceFeatureExtractor` into the answer run completion path — extract and persist feature_vector before SSE `completed` event.
- [ ] 4.4 Handle abstain/clarify routes: compute partial feature vector with available data; set unavailable features to 0.0.

## 5. Application layer — calibration scorer

- [ ] 5.1 Implement `ConfidenceScorer.score(feature_vector, profile_id) → float | None`: load active model from cache or object store; return None if no active model.
- [ ] 5.2 Implement in-process model cache keyed by `calibration_model_version.id`; invalidate on promotion.
- [ ] 5.3 Apply abstention threshold: if score < `confidence_config.abstention_threshold` → override query route to `abstain`.
- [ ] 5.4 Emit `confidence_score`, `abstention_threshold`, `calibration_model_id` in SSE `completed` event only when `emit_numeric_score=true` and score is not None.

## 6. Application layer — calibration dataset management

- [ ] 6.1 Implement `ImportCalibrationFixture` use case: validate CSV rows (label enum, chunk IDs belong to tenant), persist fixture and entries, return import summary.
- [ ] 6.2 Implement `LabelAnswerRun` use case: create or update `calibration_fixture_entry` for an answer run, increment fixture entry_count atomically.
- [ ] 6.3 Implement `BulkLabelAnswerRuns` use case: batch version of `LabelAnswerRun`, all-or-nothing transaction.
- [ ] 6.4 Implement `SyntheticFixtureGenerator` use case (BullMQ worker task): sample chunks, generate query-answer pairs via generation port, assign programmatic labels (chunk_coverage_ratio threshold), persist as `source=SYNTHETIC_BOOTSTRAP`.
- [ ] 6.5 Validate: block calibration run if `count_labeled_entries` with `source=OPERATOR_LABELED` < `min_labeled_entries`.

## 7. Application layer — calibration model training

- [ ] 7.1 Implement `CalibrationRunner` use case (called from FastAPI internal endpoint): load fixture entries from `ICalibrationFixtureRepository`, build feature matrix X from persisted feature vectors, build label vector y (SUPPORTED=1.0, PARTIALLY_SUPPORTED=0.6, UNSUPPORTED=0.2, ABSTAIN=0.0), run `IsotonicRegression(increasing=True, out_of_bounds="clip")` via `run_in_executor` on 80% split, evaluate on 20% held-out split, compute P-R curve, serialize model to object store via `calibration/` prefix (joblib), persist `calibration_model_version` with `is_active=False`.
- [ ] 7.2 Implement `ThresholdValidator`: given a model version, compute precision/recall/F1 at a given threshold; return P-R curve as list of (threshold, precision, recall) tuples.
- [ ] 7.3 Implement P-R curve → static SVG serializer: render curve as a minimal SVG string with current threshold marker; no JS chart library.
- [ ] 7.4 Implement `CalibrationPromoter` use case: validate model is not synthetic-only if `emit_numeric_score=true`; set `is_active=True` on model, `is_active=False` on previous, update `confidence_config.active_model_id`, record `promoted_by`; invalidate in-process model cache.

## 8. HTTP interface layer

- [ ] 8.1 `GET /confidence/config/{profile_id}` — return `ConfidenceConfigResponse` for profile; default values if no record.
- [ ] 8.2 `PATCH /confidence/config/{profile_id}` — update feature_weights, abstention_threshold, emit_numeric_score, min_labeled_entries; validate range constraints; warn if min_labeled_entries < 100.
- [ ] 8.3 `GET /confidence/fixtures` — list fixtures for tenant with entry counts and active status.
- [ ] 8.4 `POST /confidence/fixtures/import` — accept multipart CSV upload; call `ImportCalibrationFixture`; return import summary.
- [ ] 8.5 `POST /confidence/fixtures/generate-synthetic` — enqueue `SyntheticFixtureGenerator` job; return 202 with job_id.
- [ ] 8.6 `GET /confidence/fixtures/{fixture_id}/entries` — paginated list of entries with labels; scope to tenant.
- [ ] 8.7 `GET /confidence/answer-runs/unlabeled` — paginated list of answer runs without fixture entries for the profile; return query preview, answer preview, answer_run_id.
- [ ] 8.8 `POST /confidence/fixtures/{fixture_id}/label` — single label entry; call `LabelAnswerRun`.
- [ ] 8.9 `POST /confidence/fixtures/{fixture_id}/label-bulk` — bulk label; call `BulkLabelAnswerRuns`.
- [ ] 8.10 `POST /confidence/calibrate/{profile_id}` — validate operator-labeled entry count >= `min_labeled_entries` (422 if not); enqueue BullMQ `CalibrationJobProcessor` job with tenant_id, profile_id, fixture_id, trace_id; return 202 with job_id.
- [ ] 8.10a `POST /internal/confidence/calibrate` — FastAPI internal endpoint (not public, authenticated by internal secret); called by Node worker; runs `CalibrationRunner` use case; returns model_version_id and P-R curve data.
- [ ] 8.10b `POST /internal/confidence/fixtures/generate-synthetic` — FastAPI internal endpoint; called by Node worker; runs `SyntheticFixtureGenerator` use case; returns fixture_id.
- [ ] 8.11 `GET /confidence/calibrate/{job_id}/status` — poll BullMQ job status via worker client; on complete return model_version_id, P-R curve SVG, f1_optimal_threshold.
- [ ] 8.12 `GET /confidence/models/{model_version_id}/threshold` — given a threshold float, return precision/recall/F1 at that threshold.
- [ ] 8.13 `POST /confidence/models/{model_version_id}/promote` — call `CalibrationPromoter`; validate synthetic lock; return updated config.
- [ ] 8.14 Add Pydantic DTOs: `ConfidenceConfigResponse`, `ConfidenceConfigUpdateRequest`, `CalibrationFixtureResponse`, `FixtureEntryResponse`, `UnlabeledAnswerRunResponse`, `LabelRequest`, `BulkLabelRequest`, `CalibrateResponse`, `ThresholdEvalResponse`, `PromoteRequest`.
- [ ] 8.15 Enforce tenant scope on all endpoints; return 403 on scope mismatch.

## 9. Worker layer (Node.js BullMQ)

- [ ] 9.1 Implement `CalibrationJobProcessor` in `apps/worker/src/`: receives job payload (tenant_id, profile_id, fixture_id, trace_id), calls `POST /internal/confidence/calibrate` FastAPI internal endpoint, updates job status to completed with model_version_id and P-R curve data on success.
- [ ] 9.2 Implement `SyntheticFixtureJobProcessor` in `apps/worker/src/`: receives job payload (tenant_id, kb_id, count, profile_id, trace_id), calls `POST /internal/confidence/fixtures/generate-synthetic` FastAPI internal endpoint, updates job status on completion.
- [ ] 9.3 Register both processors in `apps/worker/src/infrastructure/queue/create-workers.ts`.
- [ ] 9.4 Ensure both processors catch all exceptions, write failure status to job result, and do not crash the worker process.
- [ ] 9.5 Job payloads MUST contain only tenant_id, profile_id/fixture_id/kb_id, trace_id — no secrets or credentials.

## 10. OpenAPI

- [ ] 10.1 Annotate all new endpoints with tags (`confidence`), summaries, response_model, and error responses.
- [ ] 10.2 Export updated `docs/openapi.json`.

## 11. Console UI

- [ ] 11.1 Add `confidence` nav item to `apps/web/configs/console.ts` with `indent: true` and `href: "/console/settings/confidence"`.
- [ ] 11.2 Add Zod schemas to `packages/schemas/`: `confidenceConfigSchema`, `calibrationFixtureSchema`, `fixtureEntrySchema`, `unlabeledAnswerRunSchema`, `calibrationResultSchema`.
- [ ] 11.3 Add response types to `packages/types/`: `ConfidenceConfigResponse`, `CalibrationFixtureResponse`, `FixtureEntryResponse`, `UnlabeledAnswerRunResponse`, `CalibrationResultResponse`, `ThresholdEvalResponse`.
- [ ] 11.4 Add API route constants to `apps/web/constants/api-routers.ts` under `confidence`: `config`, `fixtures`, `import`, `generateSynthetic`, `entries`, `unlabeled`, `label`, `labelBulk`, `calibrate`, `calibrateStatus`, `threshold`, `promote`.
- [ ] 11.5 Add query keys to `apps/web/constants/query-keys.ts` under `confidence`: `config`, `fixtures`, `entries`, `unlabeled`, `calibrateStatus`, `models`.
- [ ] 11.6 Write hooks at `apps/web/hooks/transactions/use-confidence/index.ts`: `useConfidenceConfig`, `useUpdateConfidenceConfig`, `useCalibrationFixtures`, `useImportFixture`, `useGenerateSynthetic`, `useFixtureEntries`, `useUnlabeledRuns`, `useLabelRun`, `useBulkLabelRuns`, `useRunCalibration`, `useCalibrationStatus`, `useThresholdEval`, `usePromoteModel`.
- [ ] 11.7 Create `apps/web/app/console/settings/confidence/page.tsx` — thin wrapper.
- [ ] 11.8 Create `apps/web/app/console/settings/confidence/confidence-content.tsx` — `"use client"`, four `PanelCard` sections: Calibration Status, Dataset Management, Labeling Workbench (inline toggle), Calibration & Threshold.
- [ ] 11.9 Calibration Status section: per-profile active model version, entry count, last calibrated, emit score toggle (disabled if no active model with tooltip), abstention threshold input, min_labeled_entries input, feature weights JSON editor (textarea), Save button.
- [ ] 11.10 Dataset Management section: fixture list table (version, source badge, entry count, active badge); Upload CSV inline form (file input + submit); Generate Synthetic inline form (kb selector + count input); View Entries button toggling the labeling workbench.
- [ ] 11.11 Labeling Workbench: paginated table of unlabeled answer runs; query preview (120 chars), answer preview (120 chars), label selector (native `<select>` with SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED/ABSTAIN); Save per row; Save All button; progress bar (labeled_count / min_labeled_entries).
- [ ] 11.12 Calibration & Threshold section: Run Calibration button (disabled + tooltip if below min); polling status indicator (pending/running/complete/failed); on complete: P-R curve SVG rendered from API response; F1-optimal threshold pre-filled in number input; precision/recall/F1 display updates on threshold input change via `useThresholdEval`; Promote Model button with inline two-button confirm (Promote + Cancel); Emit Score toggle locked with warning if synthetic-only.
- [ ] 11.13 Source badges: `synthetic_bootstrap` → gray, `operator_labeled` → success color. Status badges follow console convention.
- [ ] 11.14 Verify page renders within console sidebar layout and sidebar highlights Confidence nav item as active.

## 12. Tests

- [ ] 12.1 Unit test `ConfidenceFeatureExtractor`: all six features computed correctly; partial feature vector for abstain route.
- [ ] 12.2 Unit test `ConfidenceScorer`: returns None if no active model; returns float if model active; overrides route to abstain below threshold.
- [ ] 12.3 Unit test `CalibrationRunner`: trains isotonic model on fixture entries; computes P-R curve; persists model version with is_active=False.
- [ ] 12.4 Unit test `ImportCalibrationFixture`: rejects CSV with invalid label; rejects chunk IDs outside tenant; valid import persists entries.
- [ ] 12.5 Unit test `CalibrationPromoter`: blocks emit if synthetic-only; updates active_model_id atomically; invalidates cache.
- [ ] 12.6 Unit test `ConfidenceConfig` defaults: `get_or_default` returns default config when no record exists.
- [ ] 12.7 Integration test: full answer run with calibrated scorer active → `confidence_score` present in SSE `completed` event.
- [ ] 12.8 Integration test: profile with no active model → `confidence_score` absent, `evidence_level` present.
- [ ] 12.9 Integration test: score below abstention_threshold → route overridden to abstain, no generated answer.

## 13. Deferred tracker update

- [ ] 13.1 Mark task 2.5 in `openspec/changes/rag-query-deferred-followups/tasks.md` as complete.
