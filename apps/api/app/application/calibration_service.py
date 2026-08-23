"""Calibration dataset management and dependency-light monotonic model training."""

import asyncio
import csv
import io
import pickle
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from html import escape
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.errors import DomainError
from app.domain.rag.answer_trace import AnswerRun
from app.domain.rag.answer_trace_repositories import AnswerRunRepository
from app.domain.rag.confidence import (
    FEATURE_NAMES,
    CalibrationFixture,
    CalibrationFixtureEntry,
    CalibrationFixtureRepository,
    CalibrationModelRepository,
    CalibrationModelVersion,
    CalibrationSource,
    ConfidenceConfigRepository,
    ConfidenceLabel,
    ConfidenceScorer,
    FeatureVector,
)
from app.domain.rag.repositories import ChunkRepository


LABEL_VALUES = {
    ConfidenceLabel.SUPPORTED: 1.0,
    ConfidenceLabel.PARTIALLY_SUPPORTED: 0.6,
    ConfidenceLabel.UNSUPPORTED: 0.2,
    ConfidenceLabel.ABSTAIN: 0.0,
}


@dataclass(frozen=True)
class FixtureImportSummary:
    fixture: CalibrationFixture
    imported_entries: int


@dataclass(frozen=True)
class CalibrationResult:
    model: CalibrationModelVersion
    curve: tuple[tuple[float, float, float], ...]


class CalibrationArtifactStore(Protocol):
    async def put(self, *, path: str, data: bytes) -> None: ...


class SyntheticPairGenerator(Protocol):
    async def generate(self, *, chunk_text: str, profile_id: str) -> tuple[str, str]: ...


class SyntheticChunkSource(Protocol):
    async def sample(self, *, tenant_id: str, knowledge_base_id: str, count: int) -> list[tuple[str, str]]: ...


async def import_calibration_fixture(
    fixtures: CalibrationFixtureRepository,
    chunks: ChunkRepository,
    *,
    tenant_id: str,
    retrieval_profile_id: str,
    created_by: str,
    version: str,
    csv_content: str,
) -> FixtureImportSummary:
    rows = list(csv.DictReader(io.StringIO(csv_content)))
    required = {"query", "answer", "confidence_label", "evidence_chunk_ids"}
    if not rows or not required.issubset(set(rows[0])):
        raise DomainError.invalid_calibration_fixture("CSV must include query, answer, confidence_label, and evidence_chunk_ids columns.")
    invalid: list[int] = []
    parsed: list[tuple[str, str, ConfidenceLabel, tuple[str, ...]]] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            label = ConfidenceLabel(row["confidence_label"].strip().upper())
            chunk_ids = tuple(value.strip() for value in row["evidence_chunk_ids"].split("|") if value.strip())
            if not row["query"].strip() or not row["answer"].strip() or any(not _is_uuid(value) for value in chunk_ids):
                raise ValueError
        except (KeyError, ValueError):
            invalid.append(row_number)
            continue
        parsed.append((row["query"].strip(), row["answer"].strip(), label, chunk_ids))
    if invalid:
        raise DomainError.invalid_calibration_fixture("CSV contains invalid rows.", {"rows": invalid})
    requested_ids = tuple({chunk_id for _, _, _, chunk_ids in parsed for chunk_id in chunk_ids})
    found = await chunks.find_by_ids(tenant_id=tenant_id, chunk_ids=requested_ids)
    missing = sorted(set(requested_ids).difference(chunk.id for chunk in found))
    if missing:
        raise DomainError.invalid_calibration_fixture("CSV references chunks outside the tenant.", {"chunkIds": missing})
    now = _now()
    fixture = CalibrationFixture(str(uuid4()), tenant_id, retrieval_profile_id, version, CalibrationSource.OPERATOR_LABELED, 0, True, now, created_by)
    await fixtures.deactivate_previous(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)
    saved = await fixtures.save(fixture)
    entries = [CalibrationFixtureEntry(str(uuid4()), saved.id, None, query, chunk_ids, answer, label, None, None, now) for query, answer, label, chunk_ids in parsed]
    await fixtures.append_entries(tenant_id=tenant_id, fixture_id=saved.id, entries=entries)
    return FixtureImportSummary(replace(saved, entry_count=len(entries)), len(entries))


async def label_answer_run(
    fixtures: CalibrationFixtureRepository,
    answer_runs: AnswerRunRepository,
    *,
    tenant_id: str,
    fixture_id: str,
    answer_run_id: str,
    label: ConfidenceLabel,
    annotator_id: str,
) -> int:
    answer_run = await answer_runs.find_by_id(tenant_id=tenant_id, answer_run_id=answer_run_id)
    if answer_run is None or answer_run.feature_vector is None:
        raise DomainError.invalid_calibration_fixture("Answer run must exist and have a persisted feature vector.")
    entry = _entry_from_answer_run(answer_run, fixture_id=fixture_id, label=label, annotator_id=annotator_id)
    return await fixtures.upsert_answer_run_entries(tenant_id=tenant_id, fixture_id=fixture_id, entries=[entry])


async def bulk_label_answer_runs(
    fixtures: CalibrationFixtureRepository,
    answer_runs: AnswerRunRepository,
    *,
    tenant_id: str,
    fixture_id: str,
    labels: dict[str, ConfidenceLabel],
    annotator_id: str,
) -> int:
    entries: list[CalibrationFixtureEntry] = []
    for answer_run_id, label in labels.items():
        answer_run = await answer_runs.find_by_id(tenant_id=tenant_id, answer_run_id=answer_run_id)
        if answer_run is None or answer_run.feature_vector is None:
            raise DomainError.invalid_calibration_fixture("Every answer run must exist and have a persisted feature vector.", {"answerRunId": answer_run_id})
        entries.append(_entry_from_answer_run(answer_run, fixture_id=fixture_id, label=label, annotator_id=annotator_id))
    return await fixtures.upsert_answer_run_entries(tenant_id=tenant_id, fixture_id=fixture_id, entries=entries)


async def generate_synthetic_fixture(
    fixtures: CalibrationFixtureRepository,
    source: SyntheticChunkSource,
    generator: SyntheticPairGenerator,
    *,
    tenant_id: str,
    retrieval_profile_id: str,
    knowledge_base_id: str,
    count: int,
    created_by: str,
) -> CalibrationFixture:
    if count < 1:
        raise DomainError.invalid_calibration_fixture("Synthetic fixture count must be positive.")
    samples = await source.sample(tenant_id=tenant_id, knowledge_base_id=knowledge_base_id, count=count)
    now = _now()
    fixture = CalibrationFixture(str(uuid4()), tenant_id, retrieval_profile_id, "0.1.0-synthetic", CalibrationSource.SYNTHETIC_BOOTSTRAP, 0, True, now, created_by)
    await fixtures.deactivate_previous(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)
    saved = await fixtures.save(fixture)
    entries: list[CalibrationFixtureEntry] = []
    for chunk_id, chunk_text in samples:
        query, answer = await generator.generate(chunk_text=chunk_text, profile_id=retrieval_profile_id)
        coverage = 1.0 if answer.strip() else 0.0
        label = ConfidenceLabel.SUPPORTED if coverage > 0.8 else ConfidenceLabel.PARTIALLY_SUPPORTED if coverage >= 0.4 else ConfidenceLabel.UNSUPPORTED
        entries.append(CalibrationFixtureEntry(str(uuid4()), saved.id, None, query, (chunk_id,), answer, label, None, None, now))
    await fixtures.append_entries(tenant_id=tenant_id, fixture_id=saved.id, entries=entries)
    return replace(saved, entry_count=len(entries))


async def validate_calibration_ready(configs: ConfidenceConfigRepository, fixtures: CalibrationFixtureRepository, *, tenant_id: str, retrieval_profile_id: str) -> None:
    config = await configs.get_or_default(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)
    current = await fixtures.count_labeled_entries(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)
    if current < config.min_labeled_entries:
        raise DomainError.calibration_not_ready(current=current, required=config.min_labeled_entries)


class CalibrationRunner:
    def __init__(self, fixtures: CalibrationFixtureRepository, answer_runs: AnswerRunRepository, models: CalibrationModelRepository, artifacts: CalibrationArtifactStore, configs: ConfidenceConfigRepository | None = None) -> None:
        self._fixtures = fixtures
        self._answer_runs = answer_runs
        self._models = models
        self._artifacts = artifacts
        self._configs = configs

    async def run(self, *, tenant_id: str, retrieval_profile_id: str, fixture_id: str) -> CalibrationResult:
        fixture = await self._fixtures.get(tenant_id=tenant_id, fixture_id=fixture_id)
        if fixture is None or fixture.retrieval_profile_id != retrieval_profile_id:
            raise DomainError.invalid_calibration_fixture("Calibration fixture was not found for this profile.")
        if self._configs is not None:
            config = await self._configs.get_or_default(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)
            current = await self._fixtures.count_labeled_entries(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)
            if current < config.min_labeled_entries:
                raise DomainError.calibration_not_ready(current=current, required=config.min_labeled_entries)
        entries = await self._fixtures.get_entries(tenant_id=tenant_id, fixture_id=fixture_id)
        vectors: list[tuple[FeatureVector, ConfidenceLabel]] = []
        for entry in entries:
            if entry.answer_run_id is None:
                continue
            answer_run = await self._answer_runs.find_by_id(tenant_id=tenant_id, answer_run_id=entry.answer_run_id)
            if answer_run is not None and answer_run.feature_vector is not None:
                vectors.append((answer_run.feature_vector, entry.confidence_label))
        if len(vectors) < 2:
            raise DomainError.invalid_calibration_fixture("Calibration requires at least two answer-run entries with feature vectors.")
        trained, curve, threshold, precision, recall, f1 = await asyncio.get_running_loop().run_in_executor(None, _train, vectors)
        model_id = str(uuid4())
        path = f"calibration/{tenant_id}/{retrieval_profile_id}/{model_id}.pkl"
        await self._artifacts.put(path=path, data=pickle.dumps(trained, protocol=pickle.HIGHEST_PROTOCOL))
        model = CalibrationModelVersion(model_id, tenant_id, retrieval_profile_id, fixture_id, path, FEATURE_NAMES, threshold, precision, recall, f1, len(vectors), False, _now(), None)
        return CalibrationResult(await self._models.save(model), curve)


def evaluate_threshold(scores: list[float], labels: list[float], threshold: float) -> tuple[float, float, float]:
    actual = [label >= 0.5 for label in labels]
    predicted = [score >= threshold for score in scores]
    true_positive = sum(prediction and truth for prediction, truth in zip(predicted, actual, strict=True))
    false_positive = sum(prediction and not truth for prediction, truth in zip(predicted, actual, strict=True))
    false_negative = sum(not prediction and truth for prediction, truth in zip(predicted, actual, strict=True))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


class ThresholdValidator:
    def evaluate(self, *, scores: list[float], labels: list[float], threshold: float) -> tuple[float, float, float]:
        if not 0.0 <= threshold <= 1.0:
            raise DomainError.invalid_calibration_fixture("Threshold must be between 0.0 and 1.0.")
        return evaluate_threshold(scores, labels, threshold)

    def curve(self, *, scores: list[float], labels: list[float]) -> tuple[tuple[float, float, float], ...]:
        thresholds = sorted(set(scores), reverse=True)
        return tuple((threshold, *self.evaluate(scores=scores, labels=labels, threshold=threshold)[:2]) for threshold in thresholds)


def precision_recall_svg(curve: tuple[tuple[float, float, float], ...], threshold: float, *, width: int = 360, height: int = 220) -> str:
    points = " ".join(f"{40 + recall * (width - 60):.1f},{height - 30 - precision * (height - 60):.1f}" for _, precision, recall in curve)
    marker = min(curve, key=lambda point: abs(point[0] - threshold)) if curve else (threshold, 0.0, 0.0)
    x = 40 + marker[2] * (width - 60)
    y = height - 30 - marker[1] * (height - 60)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Precision recall curve at threshold {escape(f"{threshold:.2f}")}"><path d="M40 10V{height - 30}H{width - 20}" fill="none" stroke="#64748b"/><polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="2"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#dc2626"/></svg>'


class CalibrationPromoter:
    def __init__(self, fixtures: CalibrationFixtureRepository, models: CalibrationModelRepository, configs: ConfidenceConfigRepository, scorer: ConfidenceScorer) -> None:
        self._fixtures = fixtures
        self._models = models
        self._configs = configs
        self._scorer = scorer

    async def promote(self, *, tenant_id: str, model_id: str, promoted_by: str) -> CalibrationModelVersion:
        model = await self._models.get(tenant_id=tenant_id, model_id=model_id)
        if model is None:
            raise DomainError.calibration_model_not_found()
        fixture = await self._fixtures.get(tenant_id=tenant_id, fixture_id=model.fixture_id)
        if fixture is None:
            raise DomainError.invalid_calibration_fixture("Calibration model fixture was not found.")
        config = await self._configs.get_or_default(tenant_id=tenant_id, retrieval_profile_id=model.retrieval_profile_id)
        if fixture.source is CalibrationSource.SYNTHETIC_BOOTSTRAP and config.emit_numeric_score:
            raise DomainError.synthetic_calibration_emit_locked()
        promoted = await self._models.promote(tenant_id=tenant_id, model_id=model_id, promoted_by=promoted_by)
        if promoted is None:
            raise DomainError.calibration_model_not_found()
        await self._configs.set_active_model(tenant_id=tenant_id, retrieval_profile_id=model.retrieval_profile_id, active_model_id=model_id, updated_by=promoted_by)
        self._scorer.invalidate()
        return promoted


def _entry_from_answer_run(answer_run: AnswerRun, *, fixture_id: str, label: ConfidenceLabel, annotator_id: str) -> CalibrationFixtureEntry:
    evidence = answer_run.profile_snapshot.get("selected_evidence")
    chunk_ids = tuple(str(item.get("chunk_id", item.get("chunkId"))) for item in evidence if isinstance(item, dict) and item.get("chunk_id", item.get("chunkId"))) if isinstance(evidence, list) else ()
    answer = str(answer_run.profile_snapshot.get("answer", ""))
    return CalibrationFixtureEntry(str(uuid4()), fixture_id, answer_run.id, answer_run.standalone_query or answer_run.original_query, chunk_ids, answer, label, annotator_id, _now(), _now())


def _train(entries: list[tuple[FeatureVector, ConfidenceLabel]]) -> tuple["MonotonicCalibrator", tuple[tuple[float, float, float], ...], float, float, float, float]:
    ordered = sorted(entries, key=lambda entry: _vector_score(entry[0]))
    split = max(1, int(len(ordered) * 0.8))
    train, test = ordered[:split], ordered[split:] or ordered[-1:]
    # Isotonic regression is one-dimensional; aggregate the fixed, persisted vector deterministically.
    train_points = [(_vector_score(vector), LABEL_VALUES[label]) for vector, label in train]
    model = MonotonicCalibrator.fit(train_points)
    scores = [model.predict_one(_vector_score(vector)) for vector, _ in test]
    labels = [LABEL_VALUES[label] for _, label in test]
    thresholds = sorted(set(scores), reverse=True) or [0.5]
    curve = tuple((threshold, *evaluate_threshold(scores, labels, threshold)[:2]) for threshold in thresholds)
    threshold, precision, recall = max(curve, key=lambda point: (2 * point[1] * point[2] / (point[1] + point[2]) if point[1] + point[2] else 0.0, point[0]))
    _, _, f1 = evaluate_threshold(scores, labels, threshold)
    return model, curve, threshold, precision, recall, f1


def _vector_score(vector: FeatureVector) -> float:
    return sum(vector.get(name, 0.0) for name in FEATURE_NAMES) / len(FEATURE_NAMES)


@dataclass(frozen=True)
class MonotonicCalibrator:
    boundaries: tuple[float, ...]
    values: tuple[float, ...]

    @classmethod
    def fit(cls, points: list[tuple[float, float]]) -> "MonotonicCalibrator":
        blocks: list[list[float]] = []
        for score, label in sorted(points):
            blocks.append([score, score, label, 1.0])
            while len(blocks) > 1 and blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]:
                right, left = blocks.pop(), blocks.pop()
                blocks.append([left[0], right[1], left[2] + right[2], left[3] + right[3]])
        return cls(tuple(block[1] for block in blocks), tuple(block[2] / block[3] for block in blocks))

    def predict(self, values: list[list[float]]) -> list[float]:
        return [self.predict_one(sum(row) / len(row) if row else 0.0) for row in values]

    def predict_one(self, score: float) -> float:
        for boundary, value in zip(self.boundaries, self.values, strict=True):
            if score <= boundary:
                return value
        return self.values[-1]


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
