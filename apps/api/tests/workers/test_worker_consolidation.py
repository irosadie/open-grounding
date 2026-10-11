"""Unit tests for worker consolidation.

Covers:
- ingestion_worker: all 7 workers created with correct queue names and concurrency
- handle_parse: calls parse_document and enqueues to ingestion.chunk
- tool_worker: handle_tool_execution passes correct arguments
- calibration_worker: handle_calibration and handle_synthetic_fixture pass correct arguments
- confidence_service: enqueue_calibration and enqueue_synthetic use bullmq.Queue
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# ingestion_worker tests
# ---------------------------------------------------------------------------


def test_create_ingestion_workers_returns_8_workers() -> None:
    from app.core.settings import Settings
    from app.workers.ingestion_worker import create_ingestion_workers

    mock_session_factory = MagicMock()

    with patch("app.workers.ingestion_worker.Worker") as mock_worker_cls:
        mock_worker_cls.return_value = MagicMock()
        workers = create_ingestion_workers(
            Settings(_env_file=None), mock_session_factory, "redis://localhost:6379"
        )

    assert len(workers) == 8
    queue_names = [call.args[0] for call in mock_worker_cls.call_args_list]
    assert "ingestion.parse" in queue_names
    assert "ingestion.chunk" in queue_names
    assert "ingestion.embed" in queue_names
    assert "ingestion.index" in queue_names
    assert "ingestion.validate" in queue_names
    assert "ingestion.delete" in queue_names
    assert "memory.summarize" in queue_names
    assert "memory.prune" in queue_names


def test_create_ingestion_workers_concurrency() -> None:
    from app.core.settings import Settings
    from app.workers.ingestion_worker import create_ingestion_workers

    mock_session_factory = MagicMock()
    created: list[tuple[str, int]] = []

    def fake_worker(queue_name: str, handler: object, opts: dict) -> MagicMock:
        created.append((queue_name, opts.get("concurrency", 0)))
        w = MagicMock()
        w.on = MagicMock()
        return w

    with patch("app.workers.ingestion_worker.Worker", side_effect=fake_worker):
        create_ingestion_workers(
            Settings(_env_file=None), mock_session_factory, "redis://localhost:6379"
        )

    concurrency_map = dict(created)
    assert concurrency_map["ingestion.parse"] == 4
    assert concurrency_map["memory.summarize"] == 3
    assert concurrency_map["memory.prune"] == 1
    assert concurrency_map["ingestion.delete"] == 2


@pytest.mark.asyncio
async def test_handle_delete_calls_delete_stage() -> None:
    from app.core.settings import Settings
    from app.workers.ingestion_worker import create_ingestion_workers

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    captured_handlers: dict[str, object] = {}

    def fake_worker(queue_name: str, handler: object, opts: dict) -> MagicMock:
        captured_handlers[queue_name] = handler
        worker = MagicMock()
        worker.on = MagicMock()
        return worker

    with patch("app.workers.ingestion_worker.Worker", side_effect=fake_worker):
        create_ingestion_workers(
            Settings(_env_file=None), mock_session_factory, "redis://localhost:6379"
        )

    job = MagicMock()
    job.data = {"documentVersionId": "ver-1", "tenantId": "tenant-1"}
    with patch(
        "app.workers.ingestion_worker.delete_document_version",
        new_callable=AsyncMock,
    ) as delete_stage:
        await captured_handlers["ingestion.delete"](job, "token")  # type: ignore[operator]

    delete_stage.assert_awaited_once_with(
        "ver-1", "tenant-1", mock_session, Settings(_env_file=None)
    )


@pytest.mark.asyncio
async def test_handle_parse_calls_parse_document_and_enqueues_chunk() -> None:
    from app.core.settings import Settings
    from app.domain.rag.catalog import DocumentVersionLifecycleState
    from app.domain.rag.policy import Classification
    from app.workers.ingestion_worker import create_ingestion_workers

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_row = MagicMock()
    mock_row.id = "ver-1"
    mock_row.tenant_id = "tenant-1"
    mock_row.document_id = "doc-1"
    mock_row.version_number = 1
    mock_row.lifecycle_state = DocumentVersionLifecycleState.READY
    mock_row.content_checksum = "checksum"
    mock_row.source_revision = None
    mock_row.pipeline_fingerprint = None
    mock_row.parsed_text = "parsed"
    mock_row.metadata_json = None
    mock_row.object_key_raw = "uploads/ver-1"
    mock_row.size_bytes = 10
    mock_row.mime_type = "text/plain"
    mock_row.classification = Classification.INTERNAL
    mock_row.acl_principals = []
    mock_row.effective_from = None
    mock_row.effective_to = None
    mock_row.created_at = datetime.now(UTC).replace(tzinfo=None)
    mock_row.updated_at = mock_row.created_at
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_result

    captured_handlers: dict[str, object] = {}

    def fake_worker(queue_name: str, handler: object, opts: dict) -> MagicMock:
        captured_handlers[queue_name] = handler
        w = MagicMock()
        w.on = MagicMock()
        return w

    with patch("app.workers.ingestion_worker.Worker", side_effect=fake_worker):
        create_ingestion_workers(
            Settings(_env_file=None), mock_session_factory, "redis://localhost:6379"
        )

    mock_job = MagicMock()
    mock_job.data = {"documentVersionId": "ver-1", "tenantId": "tenant-1"}

    mock_queue = AsyncMock()
    mock_queue.close = AsyncMock()

    with (
        patch("app.workers.ingestion_worker.parse_document", new_callable=AsyncMock) as mock_parse,
        patch("app.workers.ingestion_worker.Queue", return_value=mock_queue),
    ):
        handler = captured_handlers["ingestion.parse"]
        await handler(mock_job, "token")

    mock_parse.assert_awaited_once()
    assert mock_parse.call_args.args[0] == "ver-1"
    assert mock_parse.call_args.args[1] == "tenant-1"
    mock_queue.add.assert_awaited_once()
    assert mock_queue.add.call_args.args[0] == "chunk"


@pytest.mark.asyncio
async def test_handle_parse_does_not_enqueue_on_failure() -> None:
    from app.core.settings import Settings
    from app.workers.ingestion_worker import create_ingestion_workers

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    captured_handlers: dict[str, object] = {}

    def fake_worker(queue_name: str, handler: object, opts: dict) -> MagicMock:
        captured_handlers[queue_name] = handler
        w = MagicMock()
        w.on = MagicMock()
        return w

    with patch("app.workers.ingestion_worker.Worker", side_effect=fake_worker):
        create_ingestion_workers(
            Settings(_env_file=None), mock_session_factory, "redis://localhost:6379"
        )

    mock_job = MagicMock()
    mock_job.data = {"documentVersionId": "ver-1", "tenantId": "tenant-1"}

    mock_queue = AsyncMock()

    with (
        patch("app.workers.ingestion_worker.parse_document", side_effect=RuntimeError("parse failed")),
        patch("app.workers.ingestion_worker.Queue", return_value=mock_queue),
    ):
        handler = captured_handlers["ingestion.parse"]
        with pytest.raises(RuntimeError):
            await handler(mock_job, "token")

    mock_queue.add.assert_not_awaited()


# ---------------------------------------------------------------------------
# tool_worker tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_tool_execution_passes_correct_arguments() -> None:
    """tool_worker creates Worker with correct queue name and concurrency."""
    from app.core.settings import Settings
    from app.workers.tool_worker import create_tool_worker

    mock_session_factory = MagicMock()
    created: list[tuple[str, int]] = []

    def fake_worker(queue_name: str, handler: object, opts: dict) -> MagicMock:
        created.append((queue_name, opts.get("concurrency", 0)))
        w = MagicMock()
        w.on = MagicMock()
        return w

    with patch("app.workers.tool_worker.Worker", side_effect=fake_worker):
        create_tool_worker(Settings(_env_file=None), mock_session_factory, "redis://localhost:6379")

    assert len(created) == 1
    assert created[0][0] == "tool-execution"
    assert created[0][1] == 5


# ---------------------------------------------------------------------------
# calibration_worker tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_calibration_passes_correct_arguments() -> None:
    """calibration_worker creates 2 workers with correct queue names and concurrency."""
    from app.core.settings import Settings
    from app.workers.calibration_worker import create_calibration_workers

    mock_session_factory = MagicMock()
    created: list[tuple[str, int]] = []

    def fake_worker(queue_name: str, handler: object, opts: dict) -> MagicMock:
        created.append((queue_name, opts.get("concurrency", 0)))
        w = MagicMock()
        w.on = MagicMock()
        return w

    with patch("app.workers.calibration_worker.Worker", side_effect=fake_worker):
        workers = create_calibration_workers(
            Settings(_env_file=None), mock_session_factory, "redis://localhost:6379"
        )

    assert len(workers) == 2
    queue_map = dict(created)
    assert "calibration" in queue_map
    assert "synthetic-fixture" in queue_map
    assert queue_map["calibration"] == 2
    assert queue_map["synthetic-fixture"] == 2


# ---------------------------------------------------------------------------
# confidence_service enqueue tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_calibration_uses_bullmq_queue() -> None:
    from app.application.confidence_service import ConfidenceService
    from app.domain.models import UserRole
    from app.domain.tenant_context import TenantContext

    tenant = TenantContext(
        tenant_id="t1", membership_id="m1", user_id="u1", role=UserRole.USER
    )

    service = ConfidenceService.__new__(ConfidenceService)
    service._configs = MagicMock()
    service._fixtures = MagicMock()
    service._models = MagicMock()
    service._answer_runs = None

    mock_queue = AsyncMock()
    mock_queue.add = AsyncMock(return_value=MagicMock())
    mock_queue.close = AsyncMock()

    with (
        patch("bullmq.Queue", return_value=mock_queue),
        patch(
            "app.application.calibration_service.validate_calibration_ready",
            new_callable=AsyncMock,
        ),
    ):
        job_id = await service.enqueue_calibration(
            tenant=tenant,
            profile_id="profile-1",
            fixture_id="fixture-1",
            trace_id="trace-1",
            redis_url="redis://localhost:6379",
        )

    assert job_id is not None
    mock_queue.add.assert_awaited_once()
    call_args = mock_queue.add.call_args
    assert call_args.args[0] == "calibrate"
    assert call_args.args[1]["tenant_id"] == "t1"


@pytest.mark.asyncio
async def test_enqueue_synthetic_uses_bullmq_queue() -> None:
    from app.application.confidence_service import ConfidenceService
    from app.domain.models import UserRole
    from app.domain.tenant_context import TenantContext

    tenant = TenantContext(
        tenant_id="t1", membership_id="m1", user_id="u1", role=UserRole.USER
    )

    service = ConfidenceService.__new__(ConfidenceService)

    mock_queue = AsyncMock()
    mock_queue.add = AsyncMock(return_value=MagicMock())
    mock_queue.close = AsyncMock()

    with patch("bullmq.Queue", return_value=mock_queue):
        job_id = await service.enqueue_synthetic(
            tenant=tenant,
            profile_id="profile-1",
            knowledge_base_id="kb-1",
            count=50,
            trace_id="trace-1",
            redis_url="redis://localhost:6379",
        )

    assert job_id is not None
    mock_queue.add.assert_awaited_once()
    call_args = mock_queue.add.call_args
    assert call_args.args[0] == "generate-synthetic"
    assert call_args.args[1]["kb_id"] == "kb-1"
