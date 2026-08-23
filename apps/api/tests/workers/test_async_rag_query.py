"""Tests for async RAG query worker and HTTP routes.

Covers:
- handle_rag_query: success path (update_running → query → update_completed → webhook)
- handle_rag_query: failure path (update_running → query raises → update_failed → webhook → re-raise)
- _fire_webhook: fires POST with correct payload
- _fire_webhook: swallows exceptions (fire-and-forget)
- _fire_webhook: no-op when url=None
- POST /rag/query/async: 202 with jobId and conversationId
- POST /rag/query/async: 422 when webhook_url is http://
- GET /rag/query/jobs/{job_id}: 200 with correct fields
- GET /rag/query/jobs/{job_id}: 404 for cross-tenant job
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.models import UserRole
from app.domain.rag.query_job import RagQueryJob, RagQueryJobStatus
from app.domain.tenant_context import TenantContext


# ---------------------------------------------------------------------------
# Worker tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_rag_query_success_path() -> None:
    from app.workers.query_worker import create_query_worker

    job_id = str(uuid4())
    tenant_id = str(uuid4())
    user_id = str(uuid4())

    fake_result = {"answer": {"text": "42"}, "route": "grounded", "traceId": str(uuid4())}

    mock_repo = MagicMock()
    mock_repo.update_running = AsyncMock()
    mock_repo.update_completed = AsyncMock()
    mock_repo.update_failed = AsyncMock()

    mock_service = MagicMock()
    mock_service.query = AsyncMock(return_value=fake_result)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_session)

    job = MagicMock()
    job.id = job_id
    job.data = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "membership_id": str(uuid4()),
        "user_id": user_id,
        "message": "What is the policy?",
        "knowledge_base_ids": ["kb-1"],
        "conversation_id": None,
        "webhook_url": None,
        "mode": "grounded",
        "decomposition": None,
        "planner": None,
        "memory": None,
    }

    with (
        patch("app.workers.query_worker.SqlAlchemyRagQueryJobRepository", return_value=mock_repo),
        patch("app.workers.query_worker._build_rag_query_service", return_value=mock_service),
        patch("app.workers.query_worker.Worker") as mock_worker_cls,
        patch("app.workers.query_worker._fire_webhook", new_callable=AsyncMock) as mock_webhook,
    ):
        mock_worker_instance = MagicMock()
        mock_worker_instance.on = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance

        from app.core.settings import Settings
        worker = create_query_worker(Settings(_env_file=None), mock_session_factory, "redis://localhost:6379")

        # Extract the handler that was registered
        handler = mock_worker_cls.call_args[0][1]
        await handler(job, "token")

    mock_repo.update_running.assert_awaited_once_with(job_id)
    mock_repo.update_completed.assert_awaited_once_with(job_id, dict(fake_result))
    mock_repo.update_failed.assert_not_awaited()
    mock_webhook.assert_awaited_once_with(None, job_id, "completed", dict(fake_result), None)


@pytest.mark.asyncio
async def test_handle_rag_query_failure_path() -> None:
    from app.workers.query_worker import create_query_worker

    job_id = str(uuid4())
    tenant_id = str(uuid4())
    user_id = str(uuid4())

    mock_repo = MagicMock()
    mock_repo.update_running = AsyncMock()
    mock_repo.update_completed = AsyncMock()
    mock_repo.update_failed = AsyncMock()

    mock_service = MagicMock()
    mock_service.query = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_session)

    job = MagicMock()
    job.id = job_id
    job.data = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "membership_id": str(uuid4()),
        "user_id": user_id,
        "message": "What is the policy?",
        "knowledge_base_ids": ["kb-1"],
        "conversation_id": None,
        "webhook_url": "https://example.com/webhook",
        "mode": "grounded",
        "decomposition": None,
        "planner": None,
        "memory": None,
    }

    with (
        patch("app.workers.query_worker.SqlAlchemyRagQueryJobRepository", return_value=mock_repo),
        patch("app.workers.query_worker._build_rag_query_service", return_value=mock_service),
        patch("app.workers.query_worker.Worker") as mock_worker_cls,
        patch("app.workers.query_worker._fire_webhook", new_callable=AsyncMock) as mock_webhook,
    ):
        mock_worker_instance = MagicMock()
        mock_worker_instance.on = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance

        from app.core.settings import Settings
        worker = create_query_worker(Settings(_env_file=None), mock_session_factory, "redis://localhost:6379")

        handler = mock_worker_cls.call_args[0][1]
        with pytest.raises(RuntimeError, match="LLM timeout"):
            await handler(job, "token")

    mock_repo.update_running.assert_awaited_once_with(job_id)
    mock_repo.update_failed.assert_awaited_once_with(job_id, "LLM timeout")
    mock_repo.update_completed.assert_not_awaited()
    mock_webhook.assert_awaited_once_with("https://example.com/webhook", job_id, "failed", None, "LLM timeout")


@pytest.mark.asyncio
async def test_fire_webhook_posts_correct_payload() -> None:
    from app.workers.query_worker import _fire_webhook

    job_id = str(uuid4())
    mock_response = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.query_worker.httpx.AsyncClient", return_value=mock_client):
        await _fire_webhook("https://example.com/hook", job_id, "completed", {"answer": "yes"}, None)

    mock_client.post.assert_awaited_once_with(
        "https://example.com/hook",
        json={"jobId": job_id, "status": "completed", "result": {"answer": "yes"}, "error": None},
    )


@pytest.mark.asyncio
async def test_fire_webhook_swallows_exceptions() -> None:
    from app.workers.query_worker import _fire_webhook

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.query_worker.httpx.AsyncClient", return_value=mock_client):
        # Should not raise
        await _fire_webhook("https://example.com/hook", "job-1", "failed", None, "err")


@pytest.mark.asyncio
async def test_fire_webhook_no_op_when_url_is_none() -> None:
    from app.workers.query_worker import _fire_webhook

    with patch("app.workers.query_worker.httpx.AsyncClient") as mock_client_cls:
        await _fire_webhook(None, "job-1", "completed", {}, None)

    mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# HTTP route tests
# ---------------------------------------------------------------------------


def _make_client_with_overrides(
    repo_mock: MagicMock | None = None,
    queue_mock: MagicMock | None = None,
    tenant_id: str | None = None,
) -> tuple[TestClient, str, MagicMock, MagicMock]:
    from app.interfaces.http.dependencies import get_session, get_tenant_context
    from app.main import create_app

    tid = tenant_id or str(uuid4())
    uid = str(uuid4())
    tenant = TenantContext(
        tenant_id=tid,
        membership_id=str(uuid4()),
        user_id=uid,
        role=UserRole.USER,
    )

    repo = repo_mock or MagicMock()
    repo.create = AsyncMock()
    repo.get_by_id_and_tenant = AsyncMock(return_value=None)

    queue = queue_mock or MagicMock()
    queue.add = AsyncMock()
    queue.close = AsyncMock()
    queue.__aenter__ = AsyncMock(return_value=queue)
    queue.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()

    app = create_app()
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    app.dependency_overrides[get_session] = lambda: mock_session

    return TestClient(app), tid, repo, queue


@pytest.mark.asyncio
async def test_async_query_returns_202_with_job_id() -> None:
    from app.interfaces.http.dependencies import get_session, get_tenant_context
    from app.main import create_app

    tenant_id = str(uuid4())
    user_id = str(uuid4())
    tenant = TenantContext(
        tenant_id=tenant_id,
        membership_id=str(uuid4()),
        user_id=user_id,
        role=UserRole.USER,
    )
    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.create = AsyncMock()

    mock_queue = MagicMock()
    mock_queue.add = AsyncMock()
    mock_queue.close = AsyncMock()

    app = create_app()
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    app.dependency_overrides[get_session] = lambda: mock_session

    with (
        patch("app.interfaces.http.routes.SqlAlchemyRagQueryJobRepository", return_value=mock_repo),
        patch("app.interfaces.http.routes.Queue", return_value=mock_queue),
    ):
        client = TestClient(app)
        response = client.post(
            "/rag/query/async",
            json={"message": "What is the policy?", "knowledge_base_ids": ["kb-1"]},
        )

    assert response.status_code == 202
    body = response.json()
    assert "jobId" in body
    assert "conversationId" in body
    mock_repo.create.assert_awaited_once()
    mock_queue.add.assert_awaited_once()


def test_async_query_rejects_http_webhook_url() -> None:
    from app.interfaces.http.dependencies import get_session, get_tenant_context
    from app.main import create_app

    tenant = TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )
    mock_session = AsyncMock()
    app = create_app()
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    app.dependency_overrides[get_session] = lambda: mock_session

    client = TestClient(app)
    response = client.post(
        "/rag/query/async",
        json={
            "message": "test",
            "knowledge_base_ids": ["kb-1"],
            "webhook_url": "http://evil.example.com/hook",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_rag_query_job_returns_200() -> None:
    from app.interfaces.http.dependencies import get_session, get_tenant_context
    from app.main import create_app

    tenant_id = str(uuid4())
    job_id = str(uuid4())
    tenant = TenantContext(
        tenant_id=tenant_id,
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )

    now = datetime.now(UTC)
    fake_job = RagQueryJob(
        id=job_id,
        tenant_id=tenant_id,
        user_id=str(uuid4()),
        status=RagQueryJobStatus.COMPLETED,
        request={"message": "test"},
        result={"answer": {"text": "42"}, "route": "grounded"},
        error=None,
        webhook_url=None,
        created_at=now,
        completed_at=now,
    )

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_by_id_and_tenant = AsyncMock(return_value=fake_job)

    app = create_app()
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    app.dependency_overrides[get_session] = lambda: mock_session

    with patch("app.interfaces.http.routes.SqlAlchemyRagQueryJobRepository", return_value=mock_repo):
        client = TestClient(app)
        response = client.get(f"/rag/query/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["jobId"] == job_id
    assert body["status"] == "completed"
    assert body["result"] == {"answer": {"text": "42"}, "route": "grounded"}
    assert body["error"] is None
    mock_repo.get_by_id_and_tenant.assert_awaited_once_with(job_id, tenant_id)


@pytest.mark.asyncio
async def test_get_rag_query_job_returns_404_for_cross_tenant() -> None:
    from app.interfaces.http.dependencies import get_session, get_tenant_context
    from app.main import create_app

    tenant = TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )
    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.get_by_id_and_tenant = AsyncMock(return_value=None)

    app = create_app()
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    app.dependency_overrides[get_session] = lambda: mock_session

    with patch("app.interfaces.http.routes.SqlAlchemyRagQueryJobRepository", return_value=mock_repo):
        client = TestClient(app)
        response = client.get(f"/rag/query/jobs/{uuid4()}")

    assert response.status_code == 404
