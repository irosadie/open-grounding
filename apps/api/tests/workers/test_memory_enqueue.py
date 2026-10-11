from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.ingestion_worker import enqueue_memory_summarize


@pytest.mark.asyncio
async def test_enqueue_memory_summarize_preserves_payload_and_accepts_job_id() -> None:
    queue = MagicMock()
    queue.add = AsyncMock()
    queue.close = AsyncMock()

    with patch("app.workers.ingestion_worker.Queue", return_value=queue):
        await enqueue_memory_summarize(
            conversation_id="conversation-1",
            tenant_id="tenant-1",
            knowledge_base_id="kb-1",
            user_id="user-1",
            redis_url="redis://localhost:6379",
            job_id="mem:conversation-1:attempt-1",
        )

    queue.add.assert_awaited_once()
    name, payload, options = queue.add.call_args.args
    assert name == "summarize"
    assert payload == {
        "conversationId": "conversation-1",
        "tenantId": "tenant-1",
        "knowledgeBaseId": "kb-1",
        "userId": "user-1",
    }
    assert options["jobId"] == "mem:conversation-1:attempt-1"
    queue.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_memory_summarize_generates_distinct_ids_for_repeated_attempts() -> None:
    queue = MagicMock()
    queue.add = AsyncMock()
    queue.close = AsyncMock()

    with patch("app.workers.ingestion_worker.Queue", return_value=queue):
        for _ in range(2):
            await enqueue_memory_summarize(
                conversation_id="conversation-1",
                tenant_id="tenant-1",
                knowledge_base_id="kb-1",
                user_id="user-1",
                redis_url="redis://localhost:6379",
            )

    job_ids = [call.args[2]["jobId"] for call in queue.add.call_args_list]
    assert job_ids[0] != job_ids[1]
    assert all(job_id.startswith("mem:conversation-1:") for job_id in job_ids)
