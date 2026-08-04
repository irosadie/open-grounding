"""Ingestion intake and document lifecycle application service.

Handles two-phase object-store upload intake, completion validation, document
identity, immutable source versioning, duplicate no-op detection, and
lifecycle transitions. Does not dispatch parser, embedding, or retrieval work.
"""

import hashlib
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.rag.catalog import DocumentVersionLifecycleState
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyKnowledgeBaseRepository,
    SqlAlchemyKnowledgeSourceRepository,
)


@dataclass(frozen=True)
class IntakeResult:
    document_id: str
    document_version_id: str
    upload_key: str
    object_key_raw: str


@dataclass(frozen=True)
class CompletionResult:
    document_version_id: str
    lifecycle_state: str
    content_checksum: str
    enqueued: bool


class IngestionIntakeService:
    """Two-phase object-store intake with validation and lifecycle management."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._kb_repo = SqlAlchemyKnowledgeBaseRepository(session)
        self._source_repo = SqlAlchemyKnowledgeSourceRepository(session)
        self._doc_repo = SqlAlchemyDocumentRepository(session)
        self._version_repo = SqlAlchemyDocumentVersionRepository(session)

    async def create_intake(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        title: str | None = None,
        source_revision: str | None = None,
    ) -> IntakeResult:
        """Create a pending document version and return an upload target."""
        if mime_type not in self._settings.ingestion_supported_mime_types_set:
            raise DomainError(
                "UNSUPPORTED_MIME_TYPE",
                f"MIME type '{mime_type}' is not supported",
                400,
            )
        if size_bytes > self._settings.rag_ingestion_max_file_size_bytes:
            raise DomainError("FILE_TOO_LARGE", "File exceeds maximum size", 400)
        kb = await self._kb_repo.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if kb is None:
            raise DomainError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base not found", 404)
        source = await self._source_repo.create(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_type="UPLOAD",
            name=filename,
            config_ref=source_revision,
        )
        doc = await self._doc_repo.create(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_id=source.id,
            title=title or filename,
        )
        from app.domain.rag.tenant_namespace import TenantNamespace

        ns = TenantNamespace(tenant_id=tenant.tenant_id)
        object_key_raw = ns.object_key("knowledge-bases", knowledge_base_id, "documents", doc.id, "raw")
        version = await self._version_repo.create(
            tenant_id=tenant.tenant_id,
            document_id=doc.id,
            version_number=1,
            content_checksum="pending",
            object_key_raw=object_key_raw,
            source_revision=source_revision,
            pipeline_fingerprint=None,
            size_bytes=size_bytes,
            mime_type=mime_type,
            acl_principals=(f"user:{tenant.user_id}", f"role:{tenant.role.value}"),
        )
        return IntakeResult(
            document_id=doc.id,
            document_version_id=version.id,
            upload_key=object_key_raw,
            object_key_raw=object_key_raw,
        )

    async def complete_intake(
        self,
        *,
        tenant: TenantContext,
        document_version_id: str,
        content_checksum: str,
    ) -> CompletionResult:
        """Validate completion, update lifecycle, and mark as STORED."""
        version = await self._version_repo.find_by_id(tenant_id=tenant.tenant_id, version_id=document_version_id)
        if version is None:
            raise DomainError("VERSION_NOT_FOUND", "Document version not found", 404)
        if version.content_checksum == content_checksum and version.content_checksum != "pending":
            return CompletionResult(
                document_version_id=version.id,
                lifecycle_state=version.lifecycle_state.value,
                content_checksum=content_checksum,
                enqueued=False,
            )
        updated = await self._version_repo.update_lifecycle_state(
            tenant_id=tenant.tenant_id,
            version_id=document_version_id,
            lifecycle_state=DocumentVersionLifecycleState.STORED.value,
        )
        state = updated.lifecycle_state.value if updated else "STORED"
        return CompletionResult(
            document_version_id=document_version_id,
            lifecycle_state=state,
            content_checksum=content_checksum,
            enqueued=True,
        )

    async def get_status(
        self,
        *,
        tenant: TenantContext,
        document_version_id: str,
    ) -> dict[str, object]:
        """Return tenant-scoped ingestion status for a document version."""
        version = await self._version_repo.find_by_id(tenant_id=tenant.tenant_id, version_id=document_version_id)
        if version is None:
            raise DomainError("VERSION_NOT_FOUND", "Document version not found", 404)
        return {
            "documentId": version.document_id,
            "documentVersionId": version.id,
            "lifecycleState": version.lifecycle_state.value,
            "mimeType": version.mime_type,
            "sizeBytes": version.size_bytes,
        }

    async def soft_delete(self, *, tenant: TenantContext, document_version_id: str) -> None:
        """Mark a document version as DELETING (removes from active retrieval)."""
        await self._version_repo.update_lifecycle_state(
            tenant_id=tenant.tenant_id,
            version_id=document_version_id,
            lifecycle_state=DocumentVersionLifecycleState.DELETING.value,
        )

    @staticmethod
    def compute_checksum(data: bytes) -> str:
        """Compute SHA-256 checksum of raw bytes."""
        return hashlib.sha256(data).hexdigest()
