"""Parse stage — extract text from uploaded document."""

from __future__ import annotations

import io
import logging
import time

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dev_trace import get_tracer
from app.core.settings import Settings
from app.domain.rag.catalog import INGESTION_CONFIG_DEFAULTS, IngestionConfig
from app.domain.rag.elements import ParsedDocument, ParserProfile
from app.domain.rag.normalizer import QualityGate, compute_invalid_char_ratio, compute_quality, normalize_document
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag.parsers.docling_adapter import DoclingParserAdapter
from app.infrastructure.rag_catalog import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIngestionConfigRepository,
)

logger = logging.getLogger(__name__)

_DEFAULT_PARSER_PROFILE = ParserProfile(
    id="default-v1",
    pipeline="standard",
    model="layout",
    ocr_enabled=False,
    version="1",
)

# Module-level shared httpx.AsyncClient — initialised lazily, reused across jobs.
_http_client: httpx.AsyncClient | None = None


def _get_http_client(settings: Settings) -> httpx.AsyncClient:
    """Return the shared httpx.AsyncClient, creating it on first call."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=settings.docling_serve_timeout_seconds,
                write=60.0,
                pool=5.0,
            )
        )
    return _http_client


async def parse_document(
    document_version_id: str,
    tenant_id: str,
    session: AsyncSession,
    settings: Settings,
) -> str:
    """Extract text from raw document. Returns extracted text."""
    version_repo = SqlAlchemyDocumentVersionRepository(session)
    doc_repo = SqlAlchemyDocumentRepository(session)
    config_repo = SqlAlchemyIngestionConfigRepository(session)

    version = await version_repo.find_by_id(tenant_id=tenant_id, version_id=document_version_id)
    if version is None:
        raise ValueError(f"Document version {document_version_id} not found")

    # Fetch KB id via parent document to load per-KB ingestion config
    document = await doc_repo.find_by_id(tenant_id=tenant_id, document_id=version.document_id)
    kb_config = None
    if document is not None:
        kb_config = await config_repo.get_by_kb(
            tenant_id=tenant_id,
            knowledge_base_id=document.knowledge_base_id,
        )
    cfg = kb_config or INGESTION_CONFIG_DEFAULTS

    # Decrypt docling-serve API key if configured — worker use only, never logged
    docling_api_key: str | None = None
    if cfg.docling_serve_api_key_enc:
        from app.infrastructure.crypto import decrypt, get_encryption_key
        docling_api_key = decrypt(cfg.docling_serve_api_key_enc, get_encryption_key(settings))

    await version_repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="PARSING"
    )

    # Read raw file from object store
    raw_content = await _read_raw_object(version.object_key_raw, settings)

    # Parse based on MIME type — adapter selected from KB config
    mime_type = version.mime_type or "text/plain"
    parsed_doc = await _parse_with_docling_or_fallback(
        raw_content=raw_content,
        mime_type=mime_type,
        filename=version.object_key_raw,
        tenant_id=tenant_id,
        settings=settings,
        cfg=cfg,
        docling_api_key=docling_api_key,
    )

    # Normalize and compute quality
    if isinstance(parsed_doc, ParsedDocument):
        normalized = normalize_document(parsed_doc)
        is_pdf = mime_type == "application/pdf"
        quality = compute_quality(normalized.elements, is_pdf=is_pdf)
        invalid_ratio = compute_invalid_char_ratio(normalized.elements)
        text = _serialize_parsed_document(normalized)
    else:
        # fallback path returned plain str
        text = parsed_doc
        quality = None
        invalid_ratio = 0.0

    # Apply quality gate with per-KB thresholds
    if cfg.auto_review:
        next_state = "NEEDS_REVIEW"
    elif quality is not None:
        gate = QualityGate(
            min_text_coverage=cfg.min_text_coverage,
            max_invalid_char_ratio=cfg.max_invalid_char_ratio,
            min_aggregate_confidence=cfg.min_aggregate_confidence,
            min_page_coverage=cfg.min_page_coverage,
        )
        gate_result = gate.evaluate(quality, invalid_char_ratio=invalid_ratio)
        next_state = gate_result if gate_result in ("NEEDS_REVIEW", "FAILED") else "NEEDS_REVIEW"
        # Only skip review (go to next stage) if gate returns READY
        if gate_result == "READY":
            next_state = "NORMALIZING"
        elif gate_result == "FAILED":
            next_state = "FAILED"
        else:
            next_state = "NEEDS_REVIEW"
    else:
        next_state = "NEEDS_REVIEW"

    # Store parsed text and set lifecycle state
    tracer = get_tracer()
    async with tracer.op(
        "ingestion.parse",
        version_id=document_version_id,
        chars=len(text),
        next_state=next_state,
        verbose_meta={"mime_type": mime_type},
    ):
        await version_repo.update_parsed_text(
            tenant_id=tenant_id,
            version_id=document_version_id,
            parsed_text=text,
        )
        await version_repo.update_lifecycle_state(
            tenant_id=tenant_id, version_id=document_version_id, lifecycle_state=next_state
        )

    logger.info("[parse] %s chars, state=%s for %s", len(text), next_state, document_version_id)
    return text


async def _parse_with_docling_or_fallback(
    *,
    raw_content: bytes,
    mime_type: str,
    filename: str,
    tenant_id: str,
    settings: Settings,
    cfg: IngestionConfig,
    docling_api_key: str | None = None,
) -> ParsedDocument | str:
    """Parse document using the adapter selected by KB IngestionConfig.parser.

    Selection:
      "docling_serve"    → DoclingServeAdapter (KB URL > Settings URL, error if neither)
      "docling_inprocess"→ DoclingParserAdapter, no pdfminer fallback
      "pdfminer"         → _extract_text() directly
      "auto"             → existing chain: serve → in-process → pdfminer
    """
    from app.domain.errors import DomainError

    tenant = TenantContext(tenant_id=tenant_id, membership_id=tenant_id, user_id=tenant_id)
    tracer = get_tracer()
    parser = cfg.parser

    # --- docling_serve: explicit, no silent fallback ----------------------------
    if parser == "docling_serve":
        serve_url = cfg.docling_serve_url or settings.docling_serve_url
        if not serve_url:
            raise DomainError(
                "DOCLING_SERVE_URL_NOT_CONFIGURED",
                "parser='docling_serve' requires docling_serve_url on the KB config or DOCLING_SERVE_URL env var",
                500,
            )
        return await _run_serve_adapter(
            serve_url=serve_url,
            raw_content=raw_content,
            mime_type=mime_type,
            filename=filename,
            tenant=tenant,
            settings=settings,
            tracer=tracer,
            api_key=docling_api_key,
        )

    # --- docling_inprocess: explicit, no pdfminer fallback ----------------------
    if parser == "docling_inprocess":
        adapter = DoclingParserAdapter(
            expected_tenant_id=tenant_id,
            profile=_DEFAULT_PARSER_PROFILE,
        )
        return await adapter.parse(
            tenant=tenant,
            source=raw_content,
            mime_type=mime_type,
            parser_profile_id=_DEFAULT_PARSER_PROFILE.id,
        )

    # --- pdfminer: explicit, skip docling entirely ------------------------------
    if parser == "pdfminer":
        return _extract_text(raw_content, mime_type, filename)

    # --- auto: existing chain serve → in-process → pdfminer --------------------
    if settings.docling_serve_url:
        return await _run_serve_adapter(
            serve_url=settings.docling_serve_url,
            raw_content=raw_content,
            mime_type=mime_type,
            filename=filename,
            tenant=tenant,
            settings=settings,
            tracer=tracer,
            api_key=docling_api_key,
        )

    try:
        adapter_ip = DoclingParserAdapter(
            expected_tenant_id=tenant_id,
            profile=_DEFAULT_PARSER_PROFILE,
        )
        return await adapter_ip.parse(
            tenant=tenant,
            source=raw_content,
            mime_type=mime_type,
            parser_profile_id=_DEFAULT_PARSER_PROFILE.id,
        )
    except DomainError as exc:
        if getattr(exc, "code", None) == "PARSER_NOT_INSTALLED":
            logger.warning("[parse] docling not installed, falling back to pdfminer for %s", filename)
            return _extract_text(raw_content, mime_type, filename)
        raise
    except ImportError:
        logger.warning("[parse] docling import failed, falling back to pdfminer for %s", filename)
        return _extract_text(raw_content, mime_type, filename)


async def _run_serve_adapter(
    *,
    serve_url: str,
    raw_content: bytes,
    mime_type: str,
    filename: str,
    tenant: TenantContext,
    settings: Settings,
    tracer: object,
    api_key: str | None = None,
) -> ParsedDocument:
    """Run DoclingServeAdapter and emit a dev_trace span."""
    from app.infrastructure.rag.parsers.docling_serve_adapter import DoclingServeAdapter

    http_client = _get_http_client(settings)
    adapter = DoclingServeAdapter(
        base_url=serve_url,
        expected_tenant_id=tenant.tenant_id,
        profile=_DEFAULT_PARSER_PROFILE,
        http_client=http_client,
        poll_interval=settings.docling_serve_poll_interval_seconds,
        timeout=settings.docling_serve_timeout_seconds,
        api_key=api_key,
    )
    t0 = time.monotonic()
    result = await adapter.parse(
        tenant=tenant,
        source=raw_content,
        mime_type=mime_type,
        parser_profile_id=_DEFAULT_PARSER_PROFILE.id,
    )
    elapsed = time.monotonic() - t0
    serialized = _serialize_parsed_document(result)
    async with tracer.op(  # type: ignore[union-attr]
        "ingestion.parse.docling_serve",
        version_id=filename,
        chars=len(serialized),
        elapsed_seconds=round(elapsed, 2),
        verbose_meta={"mime_type": mime_type, "elements": len(result.elements)},
    ):
        pass
    return result


def _serialize_parsed_document(parsed_doc: ParsedDocument) -> str:
    """Serialize ParsedDocument to plain text for downstream chunking compatibility."""
    return "\n".join(e.text for e in parsed_doc.elements if e.text.strip())


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
