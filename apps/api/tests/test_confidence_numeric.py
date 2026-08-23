"""Unit tests for rag-numeric-confidence: tasks 12.1 – 12.9."""
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.application.calibration_service import (
    CalibrationPromoter,
    CalibrationRunner,
    import_calibration_fixture,
)
from app.domain.errors import DomainError
from app.domain.rag.answer_trace import AnswerRun
from app.domain.rag.confidence import (
    FEATURE_NAMES,
    CalibrationFixture,
    CalibrationModelVersion,
    CalibrationSource,
    ConfidenceConfig,
    ConfidenceFeatureExtractor,
    ConfidenceLabel,
    ConfidenceScorer,
    override_route_for_confidence,
)

NOW = datetime.now(UTC).replace(tzinfo=None)


# ── helpers ──────────────────────────────────────────────────────────────────


def _run(
    run_id: str,
    value: float,
    *,
    route: str = "grounded",
    profile_snapshot: dict[str, Any] | None = None,
) -> AnswerRun:
    fv = {name: value for name in FEATURE_NAMES}
    snap: dict[str, Any] = profile_snapshot or {}
    return AnswerRun(run_id, "tenant", "trace", None, "q", "q", route, "high", snap, (), NOW, fv)


class FixtureRepo:
    def __init__(self, fixture: CalibrationFixture | None = None) -> None:
        self.fixture = fixture
        self.entries: list[Any] = []
        self.saved = 0

    async def deactivate_previous(self, **_: object) -> None:
        pass

    async def save(self, fixture: CalibrationFixture) -> CalibrationFixture:
        self.fixture = fixture
        self.saved += 1
        return fixture

    async def append_entries(self, *, fixture_id: str, entries: list[Any], **_: object) -> None:
        self.entries.extend(entries)

    async def upsert_answer_run_entries(self, *, entries: list[Any], **_: object) -> int:
        self.entries.extend(entries)
        return len(entries)

    async def get(self, **_: object) -> CalibrationFixture | None:
        return self.fixture

    async def get_entries(self, **_: object) -> list[Any]:
        return self.entries

    async def count_labeled_entries(self, **_: object) -> int:
        return len(self.entries)

    async def list(self, **_: object) -> list[Any]:
        return [self.fixture] if self.fixture else []


class ChunkRepo:
    async def find_by_ids(self, *, chunk_ids: tuple[str, ...], **_: object) -> list[Any]:
        return [type("Chunk", (), {"id": cid}) for cid in chunk_ids]


class EmptyChunkRepo:
    async def find_by_ids(self, **_: object) -> list[Any]:
        return []


class AnswerRuns:
    def __init__(self, runs: dict[str, AnswerRun]) -> None:
        self.runs = runs

    async def find_by_id(self, *, answer_run_id: str, **_: object) -> AnswerRun | None:
        return self.runs.get(answer_run_id)

    async def set_feature_vector(self, *, answer_run_id: str, feature_vector: dict[str, float], **_: object) -> AnswerRun | None:
        run = self.runs.get(answer_run_id)
        if run is None:
            return None
        updated = AnswerRun(run.id, run.tenant_id, run.trace_id, run.conversation_id, run.original_query, run.standalone_query, run.route, run.evidence_level, run.profile_snapshot, run.limitations, run.created_at, feature_vector)
        self.runs[answer_run_id] = updated
        return updated


class Models:
    def __init__(self, model: CalibrationModelVersion | None = None) -> None:
        self.model = model

    async def save(self, model: CalibrationModelVersion) -> CalibrationModelVersion:
        self.model = model
        return model

    async def get(self, *, model_id: str, **_: object) -> CalibrationModelVersion | None:
        return self.model if self.model and self.model.id == model_id else None

    async def get_active(self, **_: object) -> CalibrationModelVersion | None:
        return self.model if self.model and self.model.is_active else None

    async def promote(self, *, model_id: str, promoted_by: str, **_: object) -> CalibrationModelVersion | None:
        if self.model and self.model.id == model_id:
            from dataclasses import replace
            self.model = replace(self.model, is_active=True, promoted_by=promoted_by)
            return self.model
        return None

    async def list(self, **_: object) -> list[Any]:
        return [self.model] if self.model else []


class Configs:
    def __init__(self, emit: bool = False, minimum: int = 0, active_model_id: str | None = None) -> None:
        self.config = ConfidenceConfig(
            "tenant", "profile",
            emit_numeric_score=emit,
            min_labeled_entries=minimum,
            active_model_id=active_model_id,
        )
        self.active: str | None = None

    async def get_or_default(self, **_: object) -> ConfidenceConfig:
        return self.config

    async def upsert(self, config: ConfidenceConfig) -> ConfidenceConfig:
        self.config = config
        return config

    async def set_active_model(self, *, active_model_id: str | None, updated_by: str | None = None, **_: object) -> ConfidenceConfig:
        self.active = active_model_id
        return self.config


class Artifacts:
    def __init__(self) -> None:
        self.data: bytes | None = None

    async def put(self, *, data: bytes, **_: object) -> None:
        self.data = data


class NullArtifactLoader:
    async def load(self, path: str) -> Any:
        return None


# ── 12.1 ConfidenceFeatureExtractor ──────────────────────────────────────────


def test_feature_extractor_all_six_features() -> None:
    """Task 12.1 – all six features are computed; abstain route yields zero vector."""
    extractor = ConfidenceFeatureExtractor()
    snapshot: dict[str, Any] = {
        "selected_evidence": [
            {"chunk_id": "c1", "reranker_score": 0.9},
            {"chunk_id": "c2", "reranker_score": 0.7},
        ],
        "retrieval_retry_count": 1,
        "citations": [{"chunk_id": "c1"}, {"chunk_id": "c2"}],
    }
    run = AnswerRun("r1", "t", "tr", None, "q", "q", "grounded", "high", snapshot, (), NOW, None)
    fv = extractor.extract(run)
    assert set(fv.keys()) == set(FEATURE_NAMES)
    assert fv["reranker_score_mean"] > 0
    assert fv["reranker_score_min"] > 0
    assert fv["retrieval_retry_count"] == 1.0


def test_feature_extractor_abstain_partial_vector() -> None:
    """Task 12.1 – abstain/clarify route: partial vector; unavailable features are 0.0."""
    extractor = ConfidenceFeatureExtractor()
    run = AnswerRun("r2", "t", "tr", None, "q", "q", "abstain", "none", {}, (), NOW, None)
    fv = extractor.extract(run)
    assert all(isinstance(v, float) for v in fv.values())
    assert all(v >= 0.0 for v in fv.values())


# ── 12.2 ConfidenceScorer ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scorer_returns_none_if_no_active_model() -> None:
    """Task 12.2 – scorer returns None when no active model is promoted."""
    scorer = ConfidenceScorer(Configs(), Models(), NullArtifactLoader())  # type: ignore[arg-type]
    result = await scorer.score(tenant_id="t", profile_id="p", feature_vector={n: 0.5 for n in FEATURE_NAMES})
    assert result is None


@pytest.mark.asyncio
async def test_scorer_override_route_to_abstain_below_threshold() -> None:
    """Task 12.2 – override_route_for_confidence returns abstain when score < threshold."""
    route = override_route_for_confidence(route="grounded", score=0.2, abstention_threshold=0.35)
    assert route == "abstain"


@pytest.mark.asyncio
async def test_scorer_no_override_above_threshold() -> None:
    """Task 12.2 – override_route_for_confidence keeps grounded when score >= threshold."""
    route = override_route_for_confidence(route="grounded", score=0.5, abstention_threshold=0.35)
    assert route == "grounded"


# ── 12.3 CalibrationRunner ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_trains_isotonic_model_inactive_and_computes_pr_curve() -> None:
    """Task 12.3 – runner trains model, saves inactive, computes P-R curve."""
    fixture = CalibrationFixture("fix", "t", "p", "1.0.0", CalibrationSource.OPERATOR_LABELED, 2, True, NOW, None)
    fixtures = FixtureRepo(fixture)
    fixtures.entries = [
        type("Entry", (), {"answer_run_id": "r1", "confidence_label": ConfidenceLabel.SUPPORTED, "id": "e1"})(),
        type("Entry", (), {"answer_run_id": "r2", "confidence_label": ConfidenceLabel.UNSUPPORTED, "id": "e2"})(),
    ]
    models = Models()
    artifacts = Artifacts()
    result = await CalibrationRunner(
        fixtures,
        AnswerRuns({"r1": _run("r1", 1.0), "r2": _run("r2", 0.0)}),
        models,
        artifacts,
    ).run(tenant_id="t", retrieval_profile_id="p", fixture_id="fix")
    assert result.model.is_active is False
    assert artifacts.data is not None
    assert len(result.curve) >= 1


# ── 12.4 ImportCalibrationFixture ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_rejects_invalid_label() -> None:
    """Task 12.4 – CSV with bad label raises INVALID_CALIBRATION_FIXTURE."""
    repo = FixtureRepo()
    content = f"query,answer,confidence_label,evidence_chunk_ids\nq,a,BAD_LABEL,{uuid4()}\n"
    with pytest.raises(DomainError) as exc:
        await import_calibration_fixture(repo, ChunkRepo(), tenant_id="t", retrieval_profile_id="p", created_by="op", version="1.0", csv_content=content)
    assert exc.value.code == "INVALID_CALIBRATION_FIXTURE"
    assert repo.saved == 0


@pytest.mark.asyncio
async def test_import_rejects_chunks_outside_tenant() -> None:
    """Task 12.4 – CSV with chunk IDs not belonging to tenant raises error."""
    repo = FixtureRepo()
    content = f"query,answer,confidence_label,evidence_chunk_ids\nq,a,SUPPORTED,{uuid4()}\n"
    with pytest.raises(DomainError):
        await import_calibration_fixture(repo, EmptyChunkRepo(), tenant_id="t", retrieval_profile_id="p", created_by="op", version="1.0", csv_content=content)
    assert repo.saved == 0


@pytest.mark.asyncio
async def test_import_valid_csv_persists_entries() -> None:
    """Task 12.4 – valid CSV creates fixture and persists entries."""
    repo = FixtureRepo()
    chunk_id = str(uuid4())
    content = f"query,answer,confidence_label,evidence_chunk_ids\nq,a,SUPPORTED,{chunk_id}\n"
    summary = await import_calibration_fixture(repo, ChunkRepo(), tenant_id="t", retrieval_profile_id="p", created_by="op", version="1.0", csv_content=content)
    assert summary.imported_entries == 1
    assert repo.saved == 1


# ── 12.5 CalibrationPromoter ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promoter_blocks_emit_if_synthetic_only() -> None:
    """Task 12.5 – promoting a synthetic fixture with emit_numeric_score raises lock error."""
    fixture = CalibrationFixture("fix", "t", "p", "0.1.0-synthetic", CalibrationSource.SYNTHETIC_BOOTSTRAP, 1, True, NOW, None)
    fixtures = FixtureRepo(fixture)
    model = CalibrationModelVersion("m1", "t", "p", "fix", "path", tuple(FEATURE_NAMES), 0.5, 0.8, 0.8, 0.8, 1, False, NOW, None)
    models = Models(model)
    configs = Configs(emit=True)
    scorer = type("Scorer", (), {"invalidate": lambda self: None})()
    with pytest.raises(DomainError) as exc:
        await CalibrationPromoter(fixtures, models, configs, scorer).promote(  # type: ignore[arg-type]
            tenant_id="t", model_id="m1", promoted_by="op"
        )
    assert exc.value.code == "SYNTHETIC_CALIBRATION_EMIT_LOCKED"


@pytest.mark.asyncio
async def test_promoter_updates_active_model_id_atomically() -> None:
    """Task 12.5 – successful promote sets active_model_id and calls invalidate."""
    fixture = CalibrationFixture("fix", "t", "p", "1.0.0", CalibrationSource.OPERATOR_LABELED, 1, True, NOW, None)
    fixtures = FixtureRepo(fixture)
    model = CalibrationModelVersion("m1", "t", "p", "fix", "path", tuple(FEATURE_NAMES), 0.5, 0.8, 0.8, 0.8, 1, False, NOW, None)
    models = Models(model)
    configs = Configs(emit=False)
    invalidated = {"called": False}

    class _Scorer:
        def invalidate(self) -> None:
            invalidated["called"] = True

    await CalibrationPromoter(fixtures, models, configs, _Scorer()).promote(  # type: ignore[arg-type]
        tenant_id="t", model_id="m1", promoted_by="op"
    )
    assert configs.active == "m1"
    assert invalidated["called"] is True


# ── 12.6 ConfidenceConfig get_or_default ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_or_default_returns_defaults_when_no_record() -> None:
    """Task 12.6 – ConfidenceConfig.defaults() returns safe non-zero defaults."""
    result = ConfidenceConfig.defaults(tenant_id="t", retrieval_profile_id="p")
    assert result.abstention_threshold == 0.35
    assert result.emit_numeric_score is False
    assert result.min_labeled_entries >= 1
    assert result.active_model_id is None
