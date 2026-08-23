from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.calibration_service import (
    CalibrationPromoter,
    CalibrationRunner,
    MonotonicCalibrator,
    ThresholdValidator,
    import_calibration_fixture,
    precision_recall_svg,
)
from app.domain.errors import DomainError
from app.domain.rag.answer_trace import AnswerRun
from app.domain.rag.confidence import CalibrationFixture, CalibrationModelVersion, CalibrationSource, ConfidenceConfig, ConfidenceLabel, FEATURE_NAMES


NOW = datetime.now(UTC).replace(tzinfo=None)


class FixtureRepo:
    def __init__(self, fixture: CalibrationFixture | None = None) -> None:
        self.fixture = fixture
        self.entries = []
        self.saved = 0

    async def deactivate_previous(self, **_: object) -> None:
        return None

    async def save(self, fixture: CalibrationFixture) -> CalibrationFixture:
        self.fixture = fixture
        self.saved += 1
        return fixture

    async def append_entries(self, *, fixture_id: str, entries: list[object], **_: object) -> None:
        self.entries.extend(entries)

    async def upsert_answer_run_entries(self, *, entries: list[object], **_: object) -> int:
        self.entries.extend(entries)
        return len(entries)

    async def get(self, **_: object) -> CalibrationFixture | None:
        return self.fixture

    async def get_entries(self, **_: object) -> list[object]:
        return self.entries

    async def count_labeled_entries(self, **_: object) -> int:
        return len(self.entries)


class ChunkRepo:
    async def find_by_ids(self, *, chunk_ids: tuple[str, ...], **_: object) -> list[object]:
        return [type("Chunk", (), {"id": chunk_id}) for chunk_id in chunk_ids]


class EmptyChunkRepo(ChunkRepo):
    async def find_by_ids(self, **_: object) -> list[object]:
        return []


class AnswerRuns:
    def __init__(self, runs: dict[str, AnswerRun]) -> None:
        self.runs = runs

    async def find_by_id(self, *, answer_run_id: str, **_: object) -> AnswerRun | None:
        return self.runs.get(answer_run_id)


class Models:
    def __init__(self) -> None:
        self.model = None

    async def save(self, model: CalibrationModelVersion) -> CalibrationModelVersion:
        self.model = model
        return model

    async def get(self, **_: object) -> CalibrationModelVersion | None:
        return self.model

    async def promote(self, *, model_id: str, promoted_by: str, **_: object) -> CalibrationModelVersion | None:
        return self.model if self.model and self.model.id == model_id else None


class Configs:
    def __init__(self, emit: bool = False, minimum: int = 0) -> None:
        self.config = ConfidenceConfig("tenant", "profile", emit_numeric_score=emit, min_labeled_entries=minimum)
        self.active = None

    async def get_or_default(self, **_: object) -> ConfidenceConfig:
        return self.config

    async def set_active_model(self, *, active_model_id: str | None, **_: object) -> ConfidenceConfig:
        self.active = active_model_id
        return self.config


class Artifacts:
    def __init__(self) -> None:
        self.data = None

    async def put(self, *, data: bytes, **_: object) -> None:
        self.data = data


def _run(run_id: str, value: float) -> AnswerRun:
    return AnswerRun(run_id, "tenant", "trace", None, "q", "q", "grounded", "high", {}, (), NOW, {name: value for name in FEATURE_NAMES})


@pytest.mark.asyncio
async def test_import_rejects_invalid_label_and_persists_nothing() -> None:
    repo = FixtureRepo()
    content = "query,answer,confidence_label,evidence_chunk_ids\nq,a,NOPE," + str(uuid4()) + "\n"
    with pytest.raises(DomainError) as error:
        await import_calibration_fixture(repo, ChunkRepo(), tenant_id="tenant", retrieval_profile_id="profile", created_by="operator", version="1.0.0", csv_content=content)
    assert error.value.code == "INVALID_CALIBRATION_FIXTURE"
    assert repo.saved == 0


@pytest.mark.asyncio
async def test_import_rejects_chunk_from_another_tenant() -> None:
    repo = FixtureRepo()
    content = "query,answer,confidence_label,evidence_chunk_ids\nq,a,SUPPORTED," + str(uuid4()) + "\n"
    with pytest.raises(DomainError):
        await import_calibration_fixture(repo, EmptyChunkRepo(), tenant_id="tenant", retrieval_profile_id="profile", created_by="operator", version="1.0.0", csv_content=content)
    assert repo.saved == 0


def test_threshold_validator_and_svg_are_deterministic() -> None:
    validator = ThresholdValidator()
    assert validator.evaluate(scores=[0.9, 0.1], labels=[1.0, 0.0], threshold=0.5) == (1.0, 1.0, 1.0)
    svg = precision_recall_svg(validator.curve(scores=[0.9, 0.1], labels=[1.0, 0.0]), 0.5)
    assert svg.startswith("<svg") and "polyline" in svg and "circle" in svg


@pytest.mark.asyncio
async def test_runner_serializes_inactive_model_and_promoter_locks_synthetic_emit() -> None:
    fixture = CalibrationFixture("fixture", "tenant", "profile", "0.1.0-synthetic", CalibrationSource.SYNTHETIC_BOOTSTRAP, 2, True, NOW, None)
    fixtures = FixtureRepo(fixture)
    fixtures.entries = [
        type("Entry", (), {"answer_run_id": "run-1", "confidence_label": ConfidenceLabel.SUPPORTED, "id": "1"})(),
        type("Entry", (), {"answer_run_id": "run-2", "confidence_label": ConfidenceLabel.UNSUPPORTED, "id": "2"})(),
    ]
    models = Models()
    artifacts = Artifacts()
    result = await CalibrationRunner(fixtures, AnswerRuns({"run-1": _run("run-1", 1.0), "run-2": _run("run-2", 0.0)}), models, artifacts).run(tenant_id="tenant", retrieval_profile_id="profile", fixture_id="fixture")
    assert result.model.is_active is False and artifacts.data is not None
    configs = Configs(emit=True)
    scorer = type("Scorer", (), {"invalidate": lambda self: setattr(self, "invalidated", True)})()
    with pytest.raises(DomainError) as error:
        await CalibrationPromoter(fixtures, models, configs, scorer).promote(tenant_id="tenant", model_id=result.model.id, promoted_by="operator")
    assert error.value.code == "SYNTHETIC_CALIBRATION_EMIT_LOCKED"


def test_monotonic_calibrator_never_decreases() -> None:
    model = MonotonicCalibrator.fit([(0.0, 1.0), (0.5, 0.0), (1.0, 1.0)])
    predictions = model.predict([[0.0], [0.5], [1.0]])
    assert predictions == sorted(predictions)
