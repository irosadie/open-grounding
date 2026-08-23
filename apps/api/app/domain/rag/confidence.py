"""Tenant-scoped calibration entities and deterministic confidence helpers."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.domain.rag.answer_trace import AnswerRun


FEATURE_NAMES = (
    "reranker_score_mean",
    "reranker_score_min",
    "chunk_coverage_ratio",
    "source_agreement",
    "citation_validity_ratio",
    "retrieval_retry_count",
)


class ConfidenceLabel(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    ABSTAIN = "ABSTAIN"


class CalibrationSource(StrEnum):
    OPERATOR_LABELED = "OPERATOR_LABELED"
    SYNTHETIC_BOOTSTRAP = "SYNTHETIC_BOOTSTRAP"


FeatureVector = dict[str, float]


@dataclass(frozen=True)
class CalibrationFixture:
    id: str
    tenant_id: str
    retrieval_profile_id: str
    version: str
    source: CalibrationSource
    entry_count: int
    is_active: bool
    created_at: datetime
    created_by: str | None


@dataclass(frozen=True)
class CalibrationFixtureEntry:
    id: str
    fixture_id: str
    answer_run_id: str | None
    query: str
    evidence_chunk_ids: tuple[str, ...]
    answer: str
    confidence_label: ConfidenceLabel
    annotator_id: str | None
    annotated_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class CalibrationModelVersion:
    id: str
    tenant_id: str
    retrieval_profile_id: str
    fixture_id: str
    artifact_path: str
    feature_names: tuple[str, ...]
    threshold_used: float
    precision_at_threshold: float
    recall_at_threshold: float
    f1_at_threshold: float
    entry_count: int
    is_active: bool
    created_at: datetime
    promoted_by: str | None


@dataclass(frozen=True)
class ConfidenceConfig:
    tenant_id: str
    retrieval_profile_id: str
    feature_weights: dict[str, float] | None = None
    abstention_threshold: float = 0.35
    emit_numeric_score: bool = False
    min_labeled_entries: int = 200
    active_model_id: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None

    @classmethod
    def defaults(cls, *, tenant_id: str, retrieval_profile_id: str) -> "ConfidenceConfig":
        return cls(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)


class CalibrationFixtureRepository(Protocol):
    async def save(self, fixture: CalibrationFixture) -> CalibrationFixture: ...
    async def get_active(self, *, tenant_id: str, retrieval_profile_id: str) -> CalibrationFixture | None: ...
    async def list(self, *, tenant_id: str, retrieval_profile_id: str) -> list[CalibrationFixture]: ...
    async def deactivate_previous(self, *, tenant_id: str, retrieval_profile_id: str) -> None: ...
    async def append_entries(self, *, tenant_id: str, fixture_id: str, entries: list[CalibrationFixtureEntry]) -> None: ...
    async def count_labeled_entries(self, *, tenant_id: str, retrieval_profile_id: str) -> int: ...
    async def get_entries(self, *, tenant_id: str, fixture_id: str) -> list[CalibrationFixtureEntry]: ...
    async def upsert_answer_run_entries(self, *, tenant_id: str, fixture_id: str, entries: list[CalibrationFixtureEntry]) -> int: ...
    async def get(self, *, tenant_id: str, fixture_id: str) -> CalibrationFixture | None: ...


class CalibrationModelRepository(Protocol):
    async def save(self, model: CalibrationModelVersion) -> CalibrationModelVersion: ...
    async def get_active(self, *, tenant_id: str, retrieval_profile_id: str) -> CalibrationModelVersion | None: ...
    async def promote(self, *, tenant_id: str, model_id: str, promoted_by: str) -> CalibrationModelVersion | None: ...
    async def list(self, *, tenant_id: str, retrieval_profile_id: str) -> list[CalibrationModelVersion]: ...
    async def get(self, *, tenant_id: str, model_id: str) -> CalibrationModelVersion | None: ...


class ConfidenceConfigRepository(Protocol):
    async def get_or_default(self, *, tenant_id: str, retrieval_profile_id: str) -> ConfidenceConfig: ...
    async def upsert(self, config: ConfidenceConfig) -> ConfidenceConfig: ...
    async def set_active_model(self, *, tenant_id: str, retrieval_profile_id: str, active_model_id: str | None, updated_by: str | None) -> ConfidenceConfig: ...


class ConfidenceFeatureExtractor:
    """Extract the stable calibration inputs persisted with an answer run."""

    def extract(self, answer_run: AnswerRun, *, feature_weights: dict[str, float] | None = None) -> FeatureVector:
        snapshot = answer_run.profile_snapshot
        if answer_run.route in {"abstain", "clarify"}:
            raw = {name: 0.0 for name in FEATURE_NAMES}
        else:
            retrieval = _mapping(snapshot.get("retrieval_summary"))
            validation = _mapping(snapshot.get("validation_outcome"))
            evidence = _list(snapshot.get("selected_evidence"))
            scores = [_number(item.get("reranker_score", item.get("rerankerScore", 0.0))) for item in evidence]
            sources = {str(item.get("source_id", item.get("sourceId", ""))) for item in evidence if item.get("source_id", item.get("sourceId"))}
            raw = {
                "reranker_score_mean": _number(retrieval.get("reranker_score_mean", retrieval.get("rerankerScoreMean", sum(scores) / len(scores) if scores else 0.0))),
                "reranker_score_min": _number(retrieval.get("reranker_score_min", retrieval.get("rerankerScoreMin", min(scores) if scores else 0.0))),
                "chunk_coverage_ratio": _number(validation.get("chunk_coverage_ratio", validation.get("chunkCoverageRatio", 0.0))),
                "source_agreement": _number(snapshot.get("source_agreement", snapshot.get("sourceAgreement", len(sources) / len(evidence) if evidence else 0.0))),
                "citation_validity_ratio": _number(validation.get("citation_validity_ratio", validation.get("citationValidityRatio", 0.0))),
                "retrieval_retry_count": float(
                    min(1, max(0, int(_number(snapshot.get("retrieval_retry_count", snapshot.get("retrievalRetryCount", 0.0))))))
                ),
            }
        weights = feature_weights or {}
        return {name: raw[name] * _number(weights.get(name, 1.0)) for name in FEATURE_NAMES}


class CalibrationModelArtifact(Protocol):
    def predict(self, values: list[list[float]]) -> list[float]: ...


class CalibrationModelArtifactLoader(Protocol):
    async def load(self, artifact_path: str) -> CalibrationModelArtifact: ...


class ConfidenceScorer:
    def __init__(self, configs: ConfidenceConfigRepository, models: CalibrationModelRepository, artifacts: CalibrationModelArtifactLoader) -> None:
        self._configs = configs
        self._models = models
        self._artifacts = artifacts
        self._cache: dict[str, CalibrationModelArtifact] = {}

    async def score(self, *, tenant_id: str, profile_id: str, feature_vector: FeatureVector) -> float | None:
        config = await self._configs.get_or_default(tenant_id=tenant_id, retrieval_profile_id=profile_id)
        if config.active_model_id is None:
            return None
        model = await self._models.get_active(tenant_id=tenant_id, retrieval_profile_id=profile_id)
        if model is None or model.id != config.active_model_id:
            return None
        artifact = self._cache.get(model.id)
        if artifact is None:
            artifact = await self._artifacts.load(model.artifact_path)
            self._cache[model.id] = artifact
        return min(1.0, max(0.0, float(artifact.predict([[feature_vector.get(name, 0.0) for name in model.feature_names]])[0])))

    def invalidate(self, model_id: str | None = None) -> None:
        if model_id is None:
            self._cache.clear()
        else:
            self._cache.pop(model_id, None)


def override_route_for_confidence(*, route: str, score: float | None, abstention_threshold: float) -> str:
    return "abstain" if score is not None and score < abstention_threshold else route


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _number(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
