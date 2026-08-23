"""Calibration and synthetic fixture workers — BullMQ Workers.

Replaces the TypeScript calibration and synthetic-fixture processors.
Calls CalibrationRunner and generate_synthetic_fixture directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bullmq import Job, Worker

from app.core.settings import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


def create_calibration_workers(
    settings: Settings,
    session_factory: "async_sessionmaker",
    redis_url: str,
) -> list[Worker]:
    """Create BullMQ Workers for calibration and synthetic-fixture queues."""

    async def handle_calibration(job: Job, token: str) -> dict[str, object]:
        data = job.data
        tenant_id = data["tenant_id"]
        profile_id = data["profile_id"]
        fixture_id = data["fixture_id"]
        logger.info("[calibration] job=%s tenant=%s profile=%s", job.id, tenant_id, profile_id)

        from app.application.calibration_service import CalibrationRunner, precision_recall_svg
        from app.infrastructure.rag_answer_trace import SqlAlchemyAnswerRunRepository
        from app.infrastructure.rag_catalog import (
            SqlCalibrationFixtureRepository,
            SqlCalibrationModelRepository,
            SqlConfidenceConfigRepository,
        )

        class _S3ArtifactStore:
            def __init__(self, s: Settings) -> None:
                self._settings = s

            async def put(self, *, path: str, data: bytes) -> None:
                import pathlib
                if self._settings.object_store_local_path:
                    dest = pathlib.Path(self._settings.object_store_local_path) / path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    return
                import aioboto3  # type: ignore
                s3_session = aioboto3.Session()
                async with s3_session.client(
                    "s3",
                    endpoint_url=self._settings.object_store_endpoint,
                    aws_access_key_id=self._settings.object_store_access_key,
                    aws_secret_access_key=self._settings.object_store_secret_key,
                    region_name=self._settings.object_store_region,
                ) as s3:
                    await s3.put_object(
                        Bucket=self._settings.object_store_bucket, Key=path, Body=data
                    )

        async with session_factory() as session:
            runner = CalibrationRunner(
                SqlCalibrationFixtureRepository(session),
                SqlAlchemyAnswerRunRepository(session),
                SqlCalibrationModelRepository(session),
                _S3ArtifactStore(settings),
                SqlConfidenceConfigRepository(session),
            )
            result = await runner.run(
                tenant_id=tenant_id,
                retrieval_profile_id=profile_id,
                fixture_id=fixture_id,
            )

        svg = precision_recall_svg(result.curve, result.model.threshold_used)
        logger.info("[calibration] job=%s completed model=%s", job.id, result.model.id)
        return {
            "model_version_id": result.model.id,
            "pr_curve_svg": svg,
            "f1_optimal_threshold": result.model.threshold_used,
        }

    async def handle_synthetic_fixture(job: Job, token: str) -> dict[str, object]:
        data = job.data
        tenant_id = data["tenant_id"]
        profile_id = data["profile_id"]
        kb_id = data["kb_id"]
        count = int(data.get("count", 50))
        logger.info("[synthetic-fixture] job=%s tenant=%s kb=%s count=%d", job.id, tenant_id, kb_id, count)

        from app.application.calibration_service import generate_synthetic_fixture
        from app.infrastructure.rag_catalog import SqlCalibrationFixtureRepository

        class _NullChunkSource:
            async def sample(self, *, tenant_id: str, knowledge_base_id: str, count: int) -> list[tuple[str, str]]:
                return []

        class _NullPairGenerator:
            async def generate(self, *, chunk_text: str, profile_id: str) -> tuple[str, str]:
                return ("", "")

        async with session_factory() as session:
            fixture = await generate_synthetic_fixture(
                SqlCalibrationFixtureRepository(session),
                _NullChunkSource(),  # type: ignore[arg-type]
                _NullPairGenerator(),  # type: ignore[arg-type]
                tenant_id=tenant_id,
                retrieval_profile_id=profile_id,
                knowledge_base_id=kb_id,
                count=count,
                created_by="worker",
            )

        logger.info("[synthetic-fixture] job=%s completed fixture=%s", job.id, fixture.id)
        return {"fixture_id": fixture.id, "entryCount": fixture.entry_count}

    conn = {"connection": redis_url}

    calibration_worker = Worker(
        "calibration", handle_calibration, {**conn, "concurrency": 2}
    )
    synthetic_worker = Worker(
        "synthetic-fixture", handle_synthetic_fixture, {**conn, "concurrency": 2}
    )

    for w in (calibration_worker, synthetic_worker):
        w.on("failed", lambda job, err: logger.error(
            "[calibration] job=%s failed: %s", job.id if job else "?", err
        ))

    return [calibration_worker, synthetic_worker]
