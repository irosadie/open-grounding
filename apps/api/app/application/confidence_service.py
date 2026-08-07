from app.domain.errors import DomainError
from app.domain.rag.answer_trace_repositories import AnswerRunRepository
from app.domain.rag.confidence import (
    CalibrationFixtureRepository,
    CalibrationModelRepository,
    CalibrationModelVersion,
    ConfidenceConfig,
    ConfidenceConfigRepository,
    ConfidenceLabel,
)
from app.domain.tenant_context import TenantContext


class ConfidenceService:
    def __init__(
        self,
        configs: ConfidenceConfigRepository,
        fixtures: CalibrationFixtureRepository,
        models: CalibrationModelRepository,
        answer_runs: AnswerRunRepository | None = None,
    ) -> None:
        self._configs = configs
        self._fixtures = fixtures
        self._models = models
        self._answer_runs = answer_runs

    async def get_config(self, *, tenant: TenantContext, profile_id: str) -> dict[str, object]:
        config = await self._configs.get_or_default(
            tenant_id=tenant.tenant_id,
            retrieval_profile_id=profile_id,
        )
        return _config_response(config)

    async def update_config(
        self,
        *,
        tenant: TenantContext,
        profile_id: str,
        feature_weights: dict[str, float] | None,
        abstention_threshold: float | None,
        emit_numeric_score: bool | None,
        min_labeled_entries: int | None,
    ) -> dict[str, object]:
        current = await self._configs.get_or_default(
            tenant_id=tenant.tenant_id,
            retrieval_profile_id=profile_id,
        )
        emit_score = current.emit_numeric_score if emit_numeric_score is None else emit_numeric_score
        active_model_id = current.active_model_id
        if emit_score:
            active_model = await self._models.get_active(
                tenant_id=tenant.tenant_id,
                retrieval_profile_id=profile_id,
            )
            if active_model is None or active_model.id != active_model_id:
                raise DomainError("CALIBRATION_MODEL_REQUIRED", "A promoted calibration model is required to emit numeric confidence scores.", 422)
        config = ConfidenceConfig(
            tenant_id=tenant.tenant_id,
            retrieval_profile_id=profile_id,
            feature_weights=current.feature_weights if feature_weights is None else feature_weights,
            abstention_threshold=current.abstention_threshold if abstention_threshold is None else abstention_threshold,
            emit_numeric_score=emit_score,
            min_labeled_entries=current.min_labeled_entries if min_labeled_entries is None else min_labeled_entries,
            active_model_id=active_model_id,
            updated_by=tenant.user_id,
        )
        updated = await self._configs.upsert(config)
        response = _config_response(updated)
        if updated.min_labeled_entries < 100:
            response["warning"] = "Accuracy may be degraded below 100 labeled entries."
        return response

    async def list_fixtures(self, *, tenant: TenantContext, profile_id: str) -> list[dict[str, object]]:
        fixtures = await self._fixtures.list(
            tenant_id=tenant.tenant_id,
            retrieval_profile_id=profile_id,
        )
        return [
            {
                "id": fixture.id,
                "retrievalProfileId": fixture.retrieval_profile_id,
                "version": fixture.version,
                "source": fixture.source.value,
                "entryCount": fixture.entry_count,
                "isActive": fixture.is_active,
                "createdAt": fixture.created_at.isoformat(),
            }
            for fixture in fixtures
        ]

    async def get_fixture_entries(self, *, tenant: TenantContext, fixture_id: str, page: int, page_size: int) -> list[dict[str, object]]:
        fixture = await self._fixtures.get(tenant_id=tenant.tenant_id, fixture_id=fixture_id)
        if fixture is None:
            raise DomainError.not_found("Calibration fixture not found")
        entries = await self._fixtures.get_entries(tenant_id=tenant.tenant_id, fixture_id=fixture_id)
        start = (page - 1) * page_size
        paged = entries[start : start + page_size]
        return [
            {
                "id": e.id,
                "fixtureId": e.fixture_id,
                "answerRunId": e.answer_run_id,
                "query": e.query,
                "answer": e.answer,
                "confidenceLabel": e.confidence_label.value,
                "createdAt": e.created_at.isoformat(),
            }
            for e in paged
        ]

    async def get_unlabeled_runs(self, *, tenant: TenantContext, profile_id: str, page: int, page_size: int) -> list[dict[str, object]]:
        if self._answer_runs is None:
            return []
        runs = await self._answer_runs.list_unlabeled_for_profile(
            tenant_id=tenant.tenant_id,
            retrieval_profile_id=profile_id,
            page=page,
            page_size=page_size,
        )
        return [
            {
                "answerRunId": run.id,
                "queryPreview": (run.standalone_query or run.original_query or "")[:120],
                "answerPreview": str((run.profile_snapshot or {}).get("answer", ""))[:120],
            }
            for run in runs
        ]

    async def label_run(self, *, tenant: TenantContext, fixture_id: str, answer_run_id: str, label: str, annotator_id: str) -> int:
        from app.application.calibration_service import label_answer_run

        if self._answer_runs is None:
            raise DomainError("INTERNAL", "Answer run repository not available", 500)
        return await label_answer_run(
            self._fixtures,
            self._answer_runs,
            tenant_id=tenant.tenant_id,
            fixture_id=fixture_id,
            answer_run_id=answer_run_id,
            label=ConfidenceLabel(label),
            annotator_id=annotator_id,
        )

    async def bulk_label_runs(self, *, tenant: TenantContext, fixture_id: str, labels: dict[str, str], annotator_id: str) -> int:
        from app.application.calibration_service import bulk_label_answer_runs

        if self._answer_runs is None:
            raise DomainError("INTERNAL", "Answer run repository not available", 500)
        return await bulk_label_answer_runs(
            self._fixtures,
            self._answer_runs,
            tenant_id=tenant.tenant_id,
            fixture_id=fixture_id,
            labels={k: ConfidenceLabel(v) for k, v in labels.items()},
            annotator_id=annotator_id,
        )

    async def enqueue_calibration(self, *, tenant: TenantContext, profile_id: str, fixture_id: str, trace_id: str, redis_url: str) -> str:
        from uuid import uuid4

        from app.application.calibration_service import validate_calibration_ready

        await validate_calibration_ready(
            self._configs,
            self._fixtures,
            tenant_id=tenant.tenant_id,
            retrieval_profile_id=profile_id,
        )
        import json

        import redis.asyncio as aioredis

        job_id = str(uuid4())
        payload = {
            "id": job_id,
            "name": "calibrate",
            "data": {
                "tenant_id": tenant.tenant_id,
                "profile_id": profile_id,
                "fixture_id": fixture_id,
                "trace_id": trace_id,
            },
            "opts": {},
        }
        r = aioredis.from_url(redis_url)
        try:
            await r.lpush("bull:calibration:wait", json.dumps(payload))
        finally:
            await r.aclose()
        return job_id

    async def get_calibration_status(self, *, job_id: str, redis_url: str) -> dict[str, object]:
        import json

        import redis.asyncio as aioredis

        r = aioredis.from_url(redis_url)
        try:
            raw = await r.hget(f"bull:calibration:{job_id}", "returnvalue")
            state_raw = await r.hget(f"bull:calibration:{job_id}", "processedOn")
            failed = await r.hget(f"bull:calibration:{job_id}", "failedReason")
        finally:
            await r.aclose()

        if failed:
            return {"jobId": job_id, "status": "failed", "modelVersionId": None, "prCurveSvg": None, "f1OptimalThreshold": None}
        if raw:
            data = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
            return {
                "jobId": job_id,
                "status": "complete",
                "modelVersionId": data.get("model_version_id"),
                "prCurveSvg": data.get("pr_curve_svg"),
                "f1OptimalThreshold": data.get("f1_optimal_threshold"),
            }
        if state_raw:
            return {"jobId": job_id, "status": "running", "modelVersionId": None, "prCurveSvg": None, "f1OptimalThreshold": None}
        return {"jobId": job_id, "status": "pending", "modelVersionId": None, "prCurveSvg": None, "f1OptimalThreshold": None}

    async def evaluate_threshold(self, *, tenant: TenantContext, model_version_id: str, threshold: float) -> dict[str, object]:
        from app.application.calibration_service import ThresholdValidator

        model = await self._models.get(tenant_id=tenant.tenant_id, model_id=model_version_id)
        if model is None:
            raise DomainError.calibration_model_not_found()
        entries = await self._fixtures.get_entries(tenant_id=tenant.tenant_id, fixture_id=model.fixture_id)
        if self._answer_runs is None or not entries:
            return {"threshold": threshold, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        from app.application.calibration_service import LABEL_VALUES, MonotonicCalibrator, _vector_score
        import pickle
        from app.application.calibration_service import evaluate_threshold as _eval

        scores: list[float] = []
        labels_list: list[float] = []
        for entry in entries:
            if entry.answer_run_id is None:
                continue
            run = await self._answer_runs.find_by_id(tenant_id=tenant.tenant_id, answer_run_id=entry.answer_run_id)
            if run is None or run.feature_vector is None:
                continue
            scores.append(_vector_score(run.feature_vector))
            labels_list.append(LABEL_VALUES[entry.confidence_label])
        if not scores:
            return {"threshold": threshold, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        precision, recall, f1 = _eval(scores, labels_list, threshold)
        return {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1}

    async def promote_model(self, *, tenant: TenantContext, model_version_id: str, promoted_by: str, redis_url: str) -> dict[str, object]:
        from app.application.calibration_service import CalibrationPromoter
        from app.domain.rag.confidence import ConfidenceScorer
        from app.infrastructure.rag_catalog import SqlCalibrationModelRepository

        class _NullArtifactLoader:
            async def load(self, path: str) -> object:
                return None

        scorer = ConfidenceScorer(self._configs, self._models, _NullArtifactLoader())  # type: ignore[arg-type]
        promoter = CalibrationPromoter(self._fixtures, self._models, self._configs, scorer)
        promoted = await promoter.promote(
            tenant_id=tenant.tenant_id,
            model_id=model_version_id,
            promoted_by=promoted_by,
        )
        return _model_version_response(promoted)

    async def enqueue_synthetic(self, *, tenant: TenantContext, profile_id: str, knowledge_base_id: str, count: int, trace_id: str, redis_url: str) -> str:
        import json
        from uuid import uuid4

        import redis.asyncio as aioredis

        job_id = str(uuid4())
        payload = {
            "id": job_id,
            "name": "generate-synthetic",
            "data": {
                "tenant_id": tenant.tenant_id,
                "profile_id": profile_id,
                "kb_id": knowledge_base_id,
                "count": count,
                "trace_id": trace_id,
            },
            "opts": {},
        }
        r = aioredis.from_url(redis_url)
        try:
            await r.lpush("bull:synthetic-fixture:wait", json.dumps(payload))
        finally:
            await r.aclose()
        return job_id


def _config_response(config: ConfidenceConfig) -> dict[str, object]:
    return {
        "retrievalProfileId": config.retrieval_profile_id,
        "featureWeights": config.feature_weights,
        "abstentionThreshold": config.abstention_threshold,
        "emitNumericScore": config.emit_numeric_score,
        "minLabeledEntries": config.min_labeled_entries,
        "activeModelId": config.active_model_id,
        "updatedAt": config.updated_at.isoformat() if config.updated_at else None,
    }


def _model_version_response(model: CalibrationModelVersion) -> dict[str, object]:
    return {
        "id": model.id,
        "retrievalProfileId": model.retrieval_profile_id,
        "fixtureId": model.fixture_id,
        "artifactPath": model.artifact_path,
        "featureNames": list(model.feature_names),
        "thresholdUsed": model.threshold_used,
        "precisionAtThreshold": model.precision_at_threshold,
        "recallAtThreshold": model.recall_at_threshold,
        "f1AtThreshold": model.f1_at_threshold,
        "entryCount": model.entry_count,
        "isActive": model.is_active,
        "createdAt": model.created_at.isoformat(),
        "promotedBy": model.promoted_by,
    }
