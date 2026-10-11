from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.application.rag_query_service import RagQueryService
from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext


def _tenant() -> TenantContext:
    return TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )


def _service() -> RagQueryService:
    service = RagQueryService.__new__(RagQueryService)
    service._settings = Settings(_env_file=None)
    return service


@pytest.mark.asyncio
async def test_enabled_memory_enqueues_each_enabled_knowledge_base() -> None:
    service = _service()
    config_repo = MagicMock()
    config_repo.find_by_knowledge_base = AsyncMock(
        side_effect=[SimpleNamespace(enabled=True), SimpleNamespace(enabled=False)]
    )
    tenant = _tenant()

    with (
        patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository", return_value=config_repo),
        patch("app.workers.ingestion_worker.enqueue_memory_summarize", new_callable=AsyncMock) as enqueue,
    ):
        await service._enqueue_memory_summarization(
            tenant=tenant,
            conversation_id="conversation-1",
            knowledge_base_ids=("kb-enabled", "kb-disabled"),
            memory_enabled=None,
            session=object(),
        )

    enqueue.assert_awaited_once()
    assert enqueue.call_args.kwargs["knowledge_base_id"] == "kb-enabled"
    assert enqueue.call_args.kwargs["conversation_id"] == "conversation-1"
    assert enqueue.call_args.kwargs["tenant_id"] == tenant.tenant_id
    assert enqueue.call_args.kwargs["user_id"] == tenant.user_id
    assert enqueue.call_args.kwargs["job_id"].startswith("mem:conversation-1:kb-enabled:")


@pytest.mark.asyncio
async def test_explicit_memory_disable_skips_config_lookup_and_enqueue() -> None:
    service = _service()

    with (
        patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository") as config_repository,
        patch("app.workers.ingestion_worker.enqueue_memory_summarize", new_callable=AsyncMock) as enqueue,
    ):
        await service._enqueue_memory_summarization(
            tenant=_tenant(),
            conversation_id="conversation-1",
            knowledge_base_ids=("kb-1",),
            memory_enabled=False,
            session=object(),
        )

    config_repository.assert_not_called()
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_failure_is_best_effort() -> None:
    service = _service()
    config_repo = MagicMock()
    config_repo.find_by_knowledge_base = AsyncMock(return_value=SimpleNamespace(enabled=True))
    tenant = _tenant()

    with (
        patch("app.infrastructure.rag_catalog.SqlAlchemyMemoryConfigRepository", return_value=config_repo),
        patch(
            "app.workers.ingestion_worker.enqueue_memory_summarize",
            new_callable=AsyncMock,
            side_effect=RuntimeError("redis unavailable"),
        ) as enqueue,
    ):
        await service._enqueue_memory_summarization(
            tenant=tenant,
            conversation_id="conversation-1",
            knowledge_base_ids=("kb-1",),
            memory_enabled=None,
            session=object(),
        )

    enqueue.assert_awaited_once()
