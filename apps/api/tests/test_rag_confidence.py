from datetime import UTC, datetime

import pytest

from app.domain.rag.answer_trace import AnswerRun
from app.domain.rag.confidence import FEATURE_NAMES, CalibrationModelVersion, ConfidenceConfig, ConfidenceFeatureExtractor, ConfidenceScorer, override_route_for_confidence


def _answer_run(route: str = "grounded") -> AnswerRun:
    return AnswerRun(
        "run-1", "tenant-1", "trace-1", None, "question", "question", route, "high",
        {
            "retrieval_summary": {"rerankerScoreMean": 0.8, "rerankerScoreMin": 0.5},
            "validation_outcome": {"chunkCoverageRatio": 0.75, "citationValidityRatio": 0.9},
            "selected_evidence": [{"sourceId": "source-a", "rerankerScore": 0.7}, {"sourceId": "source-b", "rerankerScore": 0.9}],
            "retrievalRetryCount": 1,
        },
        (), datetime.now(UTC).replace(tzinfo=None),
    )


def test_feature_extractor_returns_all_six_weighted_deterministic_features() -> None:
    vector = ConfidenceFeatureExtractor().extract(_answer_run(), feature_weights={"reranker_score_mean": 2.0})

    assert tuple(vector) == FEATURE_NAMES
    assert vector == {"reranker_score_mean": 1.6, "reranker_score_min": 0.5, "chunk_coverage_ratio": 0.75, "source_agreement": 1.0, "citation_validity_ratio": 0.9, "retrieval_retry_count": 1.0}


def test_feature_extractor_uses_zeroes_for_abstained_answer() -> None:
    assert ConfidenceFeatureExtractor().extract(_answer_run("abstain")) == {name: 0.0 for name in FEATURE_NAMES}


class ConfigsStub:
    def __init__(self, active_model_id: str | None) -> None:
        self.config = ConfidenceConfig("tenant-1", "profile-1", active_model_id=active_model_id)

    async def get_or_default(self, *, tenant_id: str, retrieval_profile_id: str) -> ConfidenceConfig:
        assert (tenant_id, retrieval_profile_id) == ("tenant-1", "profile-1")
        return self.config


class ModelsStub:
    async def get_active(self, *, tenant_id: str, retrieval_profile_id: str) -> CalibrationModelVersion | None:
        if tenant_id != "tenant-1" or retrieval_profile_id != "profile-1":
            return None
        return CalibrationModelVersion("model-1", "tenant-1", "profile-1", "fixture-1", "calibration/model-1", FEATURE_NAMES, 0.35, 0.8, 0.7, 0.75, 200, True, datetime.now(UTC).replace(tzinfo=None), None)


class Artifact:
    def predict(self, values: list[list[float]]) -> list[float]:
        return [sum(values[0]) / len(values[0])]


class LoaderStub:
    def __init__(self) -> None:
        self.loads = 0

    async def load(self, artifact_path: str) -> Artifact:
        assert artifact_path == "calibration/model-1"
        self.loads += 1
        return Artifact()


@pytest.mark.asyncio
async def test_scorer_returns_none_without_active_model_and_caches_active_artifact() -> None:
    vector = {name: 0.6 for name in FEATURE_NAMES}
    assert await ConfidenceScorer(ConfigsStub(None), ModelsStub(), LoaderStub()).score(tenant_id="tenant-1", profile_id="profile-1", feature_vector=vector) is None

    loader = LoaderStub()
    scorer = ConfidenceScorer(ConfigsStub("model-1"), ModelsStub(), loader)
    assert await scorer.score(tenant_id="tenant-1", profile_id="profile-1", feature_vector=vector) == 0.6
    assert await scorer.score(tenant_id="tenant-1", profile_id="profile-1", feature_vector=vector) == 0.6
    assert loader.loads == 1
    scorer.invalidate("model-1")
    await scorer.score(tenant_id="tenant-1", profile_id="profile-1", feature_vector=vector)
    assert loader.loads == 2


def test_low_numeric_score_overrides_route_to_abstain() -> None:
    assert override_route_for_confidence(route="grounded", score=0.34, abstention_threshold=0.35) == "abstain"
    assert override_route_for_confidence(route="grounded", score=0.35, abstention_threshold=0.35) == "grounded"
