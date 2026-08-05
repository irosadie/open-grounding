"""Parse stage — extract text from uploaded document."""

from __future__ import annotations

import io
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.infrastructure.rag_catalog import SqlAlchemyDocumentVersionRepository

logger = logging.getLogger(__name__)


async def parse_document(
    document_version_id: str,
    tenant_id: str,
    session: AsyncSession,
    settings: Settings,
) -> str:
    """Extract text from raw document. Returns extracted text."""
    repo = SqlAlchemyDocumentVersionRepository(session)

    version = await repo.find_by_id(tenant_id=tenant_id, version_id=document_version_id)
    if version is None:
        raise ValueError(f"Document version {document_version_id} not found")

    await repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="PARSING"
    )

    # Read raw file from object store
    raw_content = await _read_raw_object(version.object_key_raw, settings)

    # Parse based on MIME type
    mime_type = version.mime_type or "text/plain"
    text = _extract_text(raw_content, mime_type, version.object_key_raw)

    # Store parsed text in object store or DB (use a simple cache approach)
    # For now store in a simple in-memory cache keyed by version_id
    _parsed_cache[document_version_id] = text

    await repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="NORMALIZING"
    )

    logger.info("[parse] extracted %d chars from %s", len(text), document_version_id)
    return text


# Simple in-process cache for parsed text (across pipeline stages in same process)
_parsed_cache: dict[str, str] = {}
_chunks_cache: dict[str, list[str]] = {}
_vectors_cache: dict[str, list[list[float]]] = {}


async def _read_raw_object(object_key: str, settings: Settings) -> bytes:
    """Read raw file bytes from object store or local path."""
    local_path = getattr(settings, "rag_object_store_local_path", None)
    if local_path:
        import os
        file_path = os.path.join(local_path, object_key)
        with open(file_path, "rb") as f:
            return f.read()
    # S3-compatible object store
    endpoint = getattr(settings, "object_store_endpoint", None)
    if endpoint:
        import aioboto3  # type: ignore
        bucket = getattr(settings, "object_store_bucket", "rag-artifacts")
        access_key = getattr(settings, "object_store_access_key", "")
        secret_key = getattr(settings, "object_store_secret_key", "")
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        ) as s3:
            response = await s3.get_object(Bucket=bucket, Key=object_key)
            return await response["Body"].read()
    raise RuntimeError("No object store configured. Set RAG_OBJECT_STORE_LOCAL_PATH or OBJECT_STORE_ENDPOINT.")


def _extract_text(content: bytes, mime_type: str, filename: str) -> str:
    """Extract plain text from document based on MIME type."""
    if mime_type == "application/pdf":
        return _extract_pdf(content)
    elif mime_type in ("text/markdown", "text/x-markdown"):
        return content.decode("utf-8", errors="replace")
    elif mime_type == "text/plain":
        return content.decode("utf-8", errors="replace")
    else:
        # Fallback: try UTF-8 decode
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            raise ValueError(f"Unsupported MIME type: {mime_type}")


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF using pdfminer."""
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams

    output = io.StringIO()
    extract_text_to_fp(io.BytesIO(content), output, laparams=LAParams())
    return output.getvalue()
