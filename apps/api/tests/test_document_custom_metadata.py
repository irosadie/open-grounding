"""Unit tests for document custom metadata feature.

Covers:
- CreateIntakeRequest validator: valid metadata → accepted
- CreateIntakeRequest validator: > 20 keys → 422
- CreateIntakeRequest validator: value bukan string → 422
- CreateIntakeRequest validator: key/value > 256 chars → 422
- metadata dipersist di DocumentVersion setelah intake
"""

import pytest
from pydantic import ValidationError

from app.interfaces.http.schemas import CreateIntakeRequest


# ---------------------------------------------------------------------------
# 7.1 — Valid metadata diterima
# ---------------------------------------------------------------------------


def test_intake_request_valid_metadata_accepted() -> None:
    req = CreateIntakeRequest(
        knowledge_base_id="kb-1",
        filename="doc.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        metadata={"author": "John", "department": "Legal"},
    )
    assert req.metadata == {"author": "John", "department": "Legal"}


def test_intake_request_no_metadata_accepted() -> None:
    req = CreateIntakeRequest(
        knowledge_base_id="kb-1",
        filename="doc.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
    )
    assert req.metadata is None


# ---------------------------------------------------------------------------
# 7.2 — > 20 keys → ValidationError
# ---------------------------------------------------------------------------


def test_intake_request_metadata_more_than_20_keys_rejected() -> None:
    metadata = {f"key_{i}": f"value_{i}" for i in range(21)}
    with pytest.raises(ValidationError) as exc_info:
        CreateIntakeRequest(
            knowledge_base_id="kb-1",
            filename="doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            metadata=metadata,
        )
    assert "20" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 7.3 — Value bukan string → ValidationError
# ---------------------------------------------------------------------------


def test_intake_request_metadata_non_string_value_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateIntakeRequest(
            knowledge_base_id="kb-1",
            filename="doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            metadata={"key": 123},  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# 7.4 — Key/value > 256 chars → ValidationError
# ---------------------------------------------------------------------------


def test_intake_request_metadata_long_key_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateIntakeRequest(
            knowledge_base_id="kb-1",
            filename="doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            metadata={"k" * 257: "value"},
        )
    assert "256" in str(exc_info.value)


def test_intake_request_metadata_long_value_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateIntakeRequest(
            knowledge_base_id="kb-1",
            filename="doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            metadata={"key": "v" * 257},
        )
    assert "256" in str(exc_info.value)


def test_intake_request_metadata_exactly_256_chars_accepted() -> None:
    req = CreateIntakeRequest(
        knowledge_base_id="kb-1",
        filename="doc.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        metadata={"k" * 256: "v" * 256},
    )
    assert req.metadata is not None


# ---------------------------------------------------------------------------
# 7.5 — metadata dipersist di DocumentVersion setelah intake
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_intake_passes_metadata_to_repo() -> None:
    from unittest.mock import AsyncMock, MagicMock
    from app.application.ingestion_intake_service import IngestionIntakeService, IntakeResult
    from app.core.settings import Settings
    from app.domain.models import UserRole
    from app.domain.tenant_context import TenantContext

    tenant = TenantContext(
        tenant_id="t1", membership_id="m1", user_id="u1", role=UserRole.USER
    )

    mock_kb = MagicMock()
    mock_kb_repo = MagicMock()
    mock_kb_repo.find_by_id = AsyncMock(return_value=mock_kb)

    mock_source = MagicMock()
    mock_source.id = "src-1"
    mock_source_repo = MagicMock()
    mock_source_repo.create = AsyncMock(return_value=mock_source)

    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc_repo = MagicMock()
    mock_doc_repo.create = AsyncMock(return_value=mock_doc)

    mock_version = MagicMock()
    mock_version.id = "ver-1"
    mock_version_repo = MagicMock()
    mock_version_repo.create = AsyncMock(return_value=mock_version)

    service = IngestionIntakeService.__new__(IngestionIntakeService)
    service._settings = Settings(_env_file=None)
    service._kb_repo = mock_kb_repo
    service._source_repo = mock_source_repo
    service._doc_repo = mock_doc_repo
    service._version_repo = mock_version_repo

    metadata = {"author": "Jane", "dept": "Finance"}
    await service.create_intake(
        tenant=tenant,
        knowledge_base_id="kb-1",
        filename="report.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        metadata=metadata,
    )

    call_kwargs = mock_version_repo.create.call_args.kwargs
    assert call_kwargs["metadata"] == metadata
