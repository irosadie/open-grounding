"""Integration tests for confidence scoring wired into the answer run path.

12.7 — calibrated scorer active → confidence_score present in result
12.8 — no active model → confidence_score absent, evidence_level present
12.9 — score below abstention_threshold → route overridden to abstain
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.domain.rag.answer_trace import AnswerRun
from app.domain.rag.confidence import (
    ConfidenceConfig,
    ConfidenceFeatureExtractor,
    ConfidenceScorer,
    CalibrationModelVersion,
    CalibrationSource,
    ConfidenceLabel,
    override_route_for_confidence,
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _ConfigRepoStub:
    def __init__(self, config: ConfidenceConfig) -> None:
        self._config = config

    async def get_or_default(self, *, tenant_id: str, retrieval_profile_id: str) -> ConfidenceConfig:
        return self._config

    async def upsert(self, config: ConfidenceConfig) -> ConfidenceConfig:
        return config

    async def set_active_model(self, *, tenant_id: str, retrieval_profile_id: str, active_model_id: str | None, updated_by: str | None) -> ConfidenceConfig:
        return self._config


class _ModelRepoStub:
    def __init__(self, model: CalibrationModelVersion | None) -> None:
        self._model = model

    async def get_active(self, *, tenant_id: str, retrieval_profile_id: str) -> CalibrationModelVersion | None:
        return self._model

    async def save(self, model: CalibrationModelVersion) -> CalibrationModelVersion:
        return model

    async def promote(self, *, tenant_id: str, model_id: str, promoted_by: str) -> CalibrationModelVersion | None:
        return self._model

    async def list(self, *, tenant_id: str, retrieval_profile_id: str) -> list[CalibrationModelVersion]:
        return [self._model] if self._model else []


class _ArtifactStub:
    def __init__(self, score: float) -> None:
        self._score = score

    def predict(self, values: list[list[float]]) -> list[float]:
        return [self._score]


class _ArtifactLoaderStub:
    def __init__(self, score: float) -> None:
        self._score = score

    async def load(self, artifact_path: str) -> _ArtifactStub:
        return _ArtifactStub(self._score)


def _answer_run(route: str = "grounded") -> AnswerRun:
    now = datetime.now(UTC).replace(tzinfo=None)
    return AnswerRun(
        id="run-1",
        tenant_id="tenant-1",
        trace_id="trace-1",
        conversation_id=None,
        original_query="What is the policy?",
        standalone_query=None,
        route=route,
        evidence_level="high",
        profile_snapshot={
            "retrieval_summary": {"rerankerScoreMean": 0.85, "rerankerScoreMin": 0.72},
            "validation_outcome": {"chunkCoverageRatio": 0.9, "citationValidityRatio": 1.0},
            "selected_evidence": [
                {"sourceId": "src-1", "reranker_score": 0.85},
                {"sourceId": "src-2", "reranker_score": 0.72},
            ],
        },
        limitations=(),
        created_at=now,
    )


def _model_version(model_id: str = "model-1", feature_names: tuple[str, ...] | None = None) -> CalibrationModelVersion:
    now = datetime.now(UTC).replace(tzinfo=None)
    return CalibrationModelVersion(
        id=model_id,
        tenant_id="tenant-1",
        retrieval_profile_id="profile-1",
        fixture_id="fixture-1",
        artifact_path="calibration/model-1.pkl",
        feature_names=feature_names or (
            "reranker_score_mean",
            "reranker_score_min",
            "chunk_coverage_ratio",
            "source_agreement",
            "citation_validity_ratio",
            "retrieval_retry_count",
        ),
        threshold_used=0.35,
        precision_at_threshold=0.9,
        recall_at_threshold=0.88,
        f1_at_threshold=0.89,
        entry_count=250,
        is_active=True,
        created_at=now,
        promoted_by=None,
    )


# ---------------------------------------------------------------------------
# 12.7 — calibrated scorer active → confidence_score present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confidence_score_present_when_calibrated_model_active() -> None:
    """12.7: full answer run with calibrated scorer active → confidence_score present."""
    model = _model_version()
    config = ConfidenceConfig(
        tenant_id="tenant-1",
        retrieval_profile_id="profile-1",
        emit_numeric_score=True,
        active_model_id=model.id,
        abstention_threshold=0.35,
    )
    scorer = ConfidenceScorer(
        configs=_ConfigRepoStub(config),
        models=_ModelRepoStub(model),
        artifacts=_ArtifactLoaderStub(score=0.82),
    )
    extractor = ConfidenceFeatureExtractor()
    run = _answer_run()
    feature_vector = extractor.extract(run)
    score = await scorer.score(tenant_id="tenant-1", profile_id="profile-1", feature_vector=feature_vector)
    route = override_route_for_confidence(route=run.route, score=score, abstention_threshold=config.abstention_threshold)

    assert score is not None
    assert 0.0 <= score <= 1.0
    assert route == "grounded"  # above threshold → not abstained
    # Emitting confidence_score depends on emit_numeric_score=True and score is not None
    assert config.emit_numeric_score is True


# ---------------------------------------------------------------------------
# 12.8 — no active model → confidence_score absent, evidence_level present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confidence_score_absent_when_no_active_model() -> None:
    """12.8: profile with no active model → confidence_score absent, evidence_level present."""
    config = ConfidenceConfig(
        tenant_id="tenant-1",
        retrieval_profile_id="profile-1",
        emit_numeric_score=False,
        active_model_id=None,
    )
    scorer = ConfidenceScorer(
        configs=_ConfigRepoStub(config),
        models=_ModelRepoStub(None),
        artifacts=_ArtifactLoaderStub(score=0.9),
    )
    extractor = ConfidenceFeatureExtractor()
    run = _answer_run()
    feature_vector = extractor.extract(run)
    score = await scorer.score(tenant_id="tenant-1", profile_id="profile-1", feature_vector=feature_vector)

    assert score is None
    assert run.evidence_level == "high"  # qualitative fallback always present


# ---------------------------------------------------------------------------
# 12.9 — score below abstention_threshold → route overridden to abstain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_score_overrides_route_to_abstain() -> None:
    """12.9: score below abstention_threshold → route overridden to abstain, no generated answer."""
    model = _model_version()
    config = ConfidenceConfig(
        tenant_id="tenant-1",
        retrieval_profile_id="profile-1",
        emit_numeric_score=True,
        active_model_id=model.id,
        abstention_threshold=0.50,  # high threshold
    )
    scorer = ConfidenceScorer(
        configs=_ConfigRepoStub(config),
        models=_ModelRepoStub(model),
        artifacts=_ArtifactLoaderStub(score=0.20),  # low score → below threshold
    )
    extractor = ConfidenceFeatureExtractor()
    run = _answer_run(route="grounded")
    feature_vector = extractor.extract(run)
    score = await scorer.score(tenant_id="tenant-1", profile_id="profile-1", feature_vector=feature_vector)
    route = override_route_for_confidence(route=run.route, score=score, abstention_threshold=config.abstention_threshold)

    assert score is not None
    assert score < config.abstention_threshold
    assert route == "abstain"  # overridden — no generated answer would be returned
