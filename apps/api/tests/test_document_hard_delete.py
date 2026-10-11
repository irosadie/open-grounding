import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.ingestion_intake_service import IngestionIntakeService
from app.core.settings import Settings
from app.domain.rag.catalog import (
    DocumentVersion,
    DocumentVersionLifecycleState,
    IndexGeneration,
    IndexGenerationStatus,
)
from app.domain.rag.policy import Classification
from app.domain.rag.profiles import IndexProfile
from app.domain.tenant_context import TenantContext
from app.infrastructure.object_store import S3ObjectStoreAdapter
from app.workers.stages.delete import delete_document_version

TENANT_ID = "tenant-1"
VERSION_ID = "version-1"


def _version(state: DocumentVersionLifecycleState) -> DocumentVersion:
    now = datetime.now(UTC).replace(tzinfo=None)
    return DocumentVersion(
        id=VERSION_ID,
        tenant_id=TENANT_ID,
        document_id="document-1",
        version_number=1,
        lifecycle_state=state,
        content_checksum="checksum",
        source_revision=None,
        pipeline_fingerprint=None,
        parsed_text="parsed text",
        metadata=None,
        object_key_raw="tenants/tenant-1/documents/document-1/raw",
        size_bytes=10,
        mime_type="text/plain",
        classification=Classification.INTERNAL,
        acl_principals=(),
        effective_from=None,
        effective_to=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_local_object_delete_is_idempotent(tmp_path: Path) -> None:
    object_key = "tenants/tenant-1/documents/document-1/raw"
    object_path = tmp_path / object_key
    object_path.parent.mkdir(parents=True)
    object_path.write_bytes(b"raw")

    adapter = S3ObjectStoreAdapter(
        Settings(_env_file=None, object_store_local_path=str(tmp_path))
    )
    await adapter.delete_object(object_key)
    await adapter.delete_object(object_key)

    assert not object_path.exists()


@pytest.mark.asyncio
async def test_delete_stage_skips_versions_not_marked_deleting() -> None:
    session = AsyncMock()
    version_repo = MagicMock()
    version_repo.find_by_id = AsyncMock(
        return_value=_version(DocumentVersionLifecycleState.READY)
    )
    generation_repo = MagicMock()

    with (
        patch(
            "app.workers.stages.delete.SqlAlchemyDocumentVersionRepository",
            return_value=version_repo,
        ),
        patch(
            "app.workers.stages.delete.SqlAlchemyIndexGenerationRepository",
            return_value=generation_repo,
        ),
    ):
        await delete_document_version(
            VERSION_ID,
            TENANT_ID,
            session,
            Settings(_env_file=None),
        )

    generation_repo.list_for_version.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_stage_cascades_external_and_database_cleanup() -> None:
    session = AsyncMock()
    session.scalar.return_value = 0
    version_repo = MagicMock()
    version_repo.find_by_id = AsyncMock(
        return_value=_version(DocumentVersionLifecycleState.DELETING)
    )
    generation_repo = MagicMock()
    generation_repo.list_for_version = AsyncMock(return_value=[])

    with (
        patch(
            "app.workers.stages.delete.SqlAlchemyDocumentVersionRepository",
            return_value=version_repo,
        ),
        patch(
            "app.workers.stages.delete.SqlAlchemyIndexGenerationRepository",
            return_value=generation_repo,
        ),
        patch(
            "app.workers.stages.delete.S3ObjectStoreAdapter"
        ) as object_store_cls,
    ):
        object_store_cls.return_value.delete_object = AsyncMock()
        await delete_document_version(
            VERSION_ID,
            TENANT_ID,
            session,
            Settings(_env_file=None),
        )

    object_store_cls.return_value.delete_object.assert_awaited_once_with(
        "tenants/tenant-1/documents/document-1/raw"
    )
    assert session.execute.await_count >= 5
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_stage_removes_vectors_for_each_generation() -> None:
    session = AsyncMock()
    session.scalar.return_value = 1
    version_repo = MagicMock()
    version_repo.find_by_id = AsyncMock(
        return_value=_version(DocumentVersionLifecycleState.DELETING)
    )
    generation_repo = MagicMock()
    generation_repo.list_for_version = AsyncMock(
        return_value=[
            IndexGeneration(
                id="generation-1",
                tenant_id=TENANT_ID,
                document_version_id=VERSION_ID,
                index_profile_id="profile-1",
                status=IndexGenerationStatus.ACTIVE,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        ]
    )
    profile_repo = MagicMock()
    profile_repo.find_by_id = AsyncMock(
        return_value=IndexProfile(
            id="profile-1",
            tenant_id=TENANT_ID,
            name="Default",
            embedding_profile_id="embedding-1",
            sparse_profile_id=None,
            reranker_profile_id=None,
            collection="rag-default",
            dimensions=3,
            distance_metric="cosine",
            chunking_strategy="RECURSIVE",
            chunk_size_tokens=400,
            chunk_overlap_tokens=50,
            parent_chunk_size=1500,
            version="1",
        )
    )
    vector_store = MagicMock()
    vector_store.delete_points = AsyncMock()

    with (
        patch(
            "app.workers.stages.delete.SqlAlchemyDocumentVersionRepository",
            return_value=version_repo,
        ),
        patch(
            "app.workers.stages.delete.SqlAlchemyIndexGenerationRepository",
            return_value=generation_repo,
        ),
        patch(
            "app.workers.stages.delete.SqlAlchemyIndexProfileRepository",
            return_value=profile_repo,
        ),
        patch(
            "app.workers.stages.delete.QdrantVectorStoreAdapter",
            return_value=vector_store,
        ),
        patch("app.workers.stages.delete.S3ObjectStoreAdapter") as object_store_cls,
    ):
        object_store_cls.return_value.delete_object = AsyncMock()
        await delete_document_version(
            VERSION_ID,
            TENANT_ID,
            session,
            Settings(_env_file=None),
        )

    vector_store.delete_points.assert_awaited_once()
    assert vector_store.delete_points.await_args.kwargs["collection"] == "rag-default"
    assert vector_store.delete_points.await_args.kwargs["document_version_id"] == VERSION_ID


@pytest.mark.asyncio
async def test_soft_delete_enqueues_delete_job_after_lifecycle_transition() -> None:
    service = IngestionIntakeService(AsyncMock(), Settings(_env_file=None))
    version_repo = MagicMock()
    version_repo.find_by_id = AsyncMock(
        return_value=SimpleNamespace(lifecycle_state=DocumentVersionLifecycleState.READY)
    )
    version_repo.update_lifecycle_state = AsyncMock()
    service._version_repo = version_repo
    service._enqueue_delete = AsyncMock()

    await service.soft_delete(
        tenant=TenantContext(
            tenant_id=TENANT_ID,
            membership_id="membership-1",
            user_id="user-1",
        ),
        document_version_id=VERSION_ID,
    )

    version_repo.update_lifecycle_state.assert_awaited_once_with(
        tenant_id=TENANT_ID,
        version_id=VERSION_ID,
        lifecycle_state="DELETING",
    )
    service._enqueue_delete.assert_awaited_once_with(
        document_version_id=VERSION_ID,
        tenant_id=TENANT_ID,
    )


@pytest.mark.asyncio
async def test_enqueue_delete_uses_expected_bullmq_payload() -> None:
    service = IngestionIntakeService(AsyncMock(), Settings(_env_file=None))
    redis = AsyncMock()
    redis.exists.return_value = False

    with patch(
        "app.application.ingestion_intake_service.aioredis.from_url",
        return_value=redis,
    ):
        await service._enqueue_delete(VERSION_ID, TENANT_ID)

    mapping = redis.hset.await_args.kwargs["mapping"]
    assert mapping["name"] == "delete"
    assert json.loads(mapping["data"]) == {
        "documentVersionId": VERSION_ID,
        "tenantId": TENANT_ID,
    }
    redis.lpush.assert_awaited_once_with(
        "bull:ingestion.delete:wait",
        f"delete:{VERSION_ID}",
    )
