"""Unit tests for kb-parser-config change.

Covers tasks 10.1–10.9:
- 10.1 upsert_config with valid parser="docling_serve" + URL → persisted
- 10.2 upsert_config with parser="docling_serve" + no URL → VALIDATION_ERROR
- 10.3 upsert_config with unknown parser → VALIDATION_ERROR
- 10.4 parse stage parser="docling_serve" uses KB URL over Settings URL
- 10.5 parse stage parser="docling_serve" falls back to Settings URL when KB URL absent
- 10.6 parse stage parser="docling_serve" no URL → DOCLING_SERVE_URL_NOT_CONFIGURED
- 10.7 parse stage parser="docling_inprocess" → DoclingParserAdapter used
- 10.8 parse stage parser="pdfminer" → _extract_text() called directly
- 10.9 parse stage parser="auto" → existing chain preserved
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.errors import DomainError
from app.domain.rag.catalog import INGESTION_CONFIG_DEFAULTS, IngestionConfig
from app.domain.rag.elements import ParsedDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(**kwargs) -> IngestionConfig:
    """Build an IngestionConfig from defaults with overrides."""
    base = {
        "id": "cfg-1",
        "tenant_id": "t1",
        "knowledge_base_id": "kb-1",
        "min_text_coverage": 0.3,
        "max_invalid_char_ratio": 0.1,
        "min_aggregate_confidence": 0.5,
        "min_page_coverage": 0.5,
        "auto_review": False,
        "parser": "auto",
        "docling_serve_url": None,
        "docling_serve_api_key_enc": None,
        "created_at": INGESTION_CONFIG_DEFAULTS.created_at,
        "updated_at": INGESTION_CONFIG_DEFAULTS.updated_at,
    }
    base.update(kwargs)
    return IngestionConfig(**base)


def _make_settings(**kwargs):
    from app.core.settings import Settings
    return Settings(**kwargs)


# ---------------------------------------------------------------------------
# 10.1 — upsert_config with valid parser="docling_serve" + URL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_config_docling_serve_valid() -> None:
    from app.application.ingestion_config_service import IngestionConfigService
    from app.core.settings import Settings

    mock_session = AsyncMock()
    svc = IngestionConfigService(mock_session)

    mock_kb = MagicMock()
    svc._kb_repo = MagicMock()
    svc._kb_repo.find_by_id = AsyncMock(return_value=mock_kb)

    expected_cfg = _make_cfg(parser="docling_serve", docling_serve_url="http://serve:5001")
    svc._repo = MagicMock()
    svc._repo.get_by_kb = AsyncMock(return_value=None)
    svc._repo.upsert = AsyncMock(return_value=expected_cfg)

    from app.domain.tenant_context import TenantContext
    tenant = TenantContext(tenant_id="t1", membership_id="t1", user_id="t1")

    result = await svc.upsert_config(
        tenant=tenant,
        knowledge_base_id="kb-1",
        min_text_coverage=0.3,
        max_invalid_char_ratio=0.1,
        min_aggregate_confidence=0.5,
        min_page_coverage=0.5,
        auto_review=False,
        parser="docling_serve",
        docling_serve_url="http://serve:5001",
        settings=Settings(),
    )

    assert result.parser == "docling_serve"
    assert result.docling_serve_url == "http://serve:5001"
    svc._repo.upsert.assert_awaited_once()


# ---------------------------------------------------------------------------
# 10.2 — parser="docling_serve" without URL → VALIDATION_ERROR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_config_docling_serve_no_url_raises() -> None:
    from app.application.ingestion_config_service import IngestionConfigService

    mock_session = AsyncMock()
    svc = IngestionConfigService(mock_session)
    svc._kb_repo = MagicMock()
    svc._kb_repo.find_by_id = AsyncMock(return_value=MagicMock())

    from app.domain.tenant_context import TenantContext
    tenant = TenantContext(tenant_id="t1", membership_id="t1", user_id="t1")

    with pytest.raises(DomainError) as exc_info:
        await svc.upsert_config(
            tenant=tenant,
            knowledge_base_id="kb-1",
            min_text_coverage=0.3,
            max_invalid_char_ratio=0.1,
            min_aggregate_confidence=0.5,
            min_page_coverage=0.5,
            auto_review=False,
            parser="docling_serve",
            docling_serve_url=None,
        )

    assert exc_info.value.code == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 10.3 — unknown parser → VALIDATION_ERROR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_config_unknown_parser_raises() -> None:
    from app.application.ingestion_config_service import IngestionConfigService

    mock_session = AsyncMock()
    svc = IngestionConfigService(mock_session)
    svc._kb_repo = MagicMock()
    svc._kb_repo.find_by_id = AsyncMock(return_value=MagicMock())

    from app.domain.tenant_context import TenantContext
    tenant = TenantContext(tenant_id="t1", membership_id="t1", user_id="t1")

    with pytest.raises(DomainError) as exc_info:
        await svc.upsert_config(
            tenant=tenant,
            knowledge_base_id="kb-1",
            min_text_coverage=0.3,
            max_invalid_char_ratio=0.1,
            min_aggregate_confidence=0.5,
            min_page_coverage=0.5,
            auto_review=False,
            parser="unknown_parser",
        )

    assert exc_info.value.code == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 10.4 — parse stage parser="docling_serve" uses KB URL over Settings URL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_docling_serve_uses_kb_url() -> None:
    from app.workers.stages import parse as parse_module

    mock_parsed = MagicMock(spec=ParsedDocument)
    mock_parsed.elements = []
    mock_parsed.quality = MagicMock()

    cfg = _make_cfg(parser="docling_serve", docling_serve_url="http://kb-serve:5001")
    settings = _make_settings(docling_serve_url="http://global-serve:5001")

    with patch("app.workers.stages.parse._run_serve_adapter", new_callable=AsyncMock) as mock_serve:
        mock_serve.return_value = mock_parsed
        parse_module._http_client = None

        result = await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="t1",
            settings=settings,
            cfg=cfg,
        )

    mock_serve.assert_awaited_once()
    call_kwargs = mock_serve.call_args.kwargs
    assert call_kwargs["serve_url"] == "http://kb-serve:5001"
    assert result is mock_parsed


# ---------------------------------------------------------------------------
# 10.5 — parse stage parser="docling_serve" falls back to Settings URL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_docling_serve_fallback_to_settings_url() -> None:
    from app.workers.stages import parse as parse_module

    mock_parsed = MagicMock(spec=ParsedDocument)
    mock_parsed.elements = []
    mock_parsed.quality = MagicMock()

    cfg = _make_cfg(parser="docling_serve", docling_serve_url=None)
    settings = _make_settings(docling_serve_url="http://global-serve:5001")

    with patch("app.workers.stages.parse._run_serve_adapter", new_callable=AsyncMock) as mock_serve:
        mock_serve.return_value = mock_parsed
        parse_module._http_client = None

        result = await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="t1",
            settings=settings,
            cfg=cfg,
        )

    call_kwargs = mock_serve.call_args.kwargs
    assert call_kwargs["serve_url"] == "http://global-serve:5001"
    assert result is mock_parsed


# ---------------------------------------------------------------------------
# 10.6 — parse stage parser="docling_serve" no URL → DOCLING_SERVE_URL_NOT_CONFIGURED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_docling_serve_no_url_raises() -> None:
    from app.workers.stages import parse as parse_module

    cfg = _make_cfg(parser="docling_serve", docling_serve_url=None)
    settings = _make_settings(docling_serve_url=None)

    with pytest.raises(DomainError) as exc_info:
        await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="t1",
            settings=settings,
            cfg=cfg,
        )

    assert exc_info.value.code == "DOCLING_SERVE_URL_NOT_CONFIGURED"


# ---------------------------------------------------------------------------
# 10.7 — parse stage parser="docling_inprocess" → DoclingParserAdapter used
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_docling_inprocess_uses_adapter() -> None:
    from app.workers.stages import parse as parse_module

    mock_parsed = MagicMock(spec=ParsedDocument)
    mock_parsed.elements = []
    mock_parsed.quality = MagicMock()

    cfg = _make_cfg(parser="docling_inprocess")
    settings = _make_settings(docling_serve_url=None)

    with patch("app.workers.stages.parse.DoclingParserAdapter", autospec=True) as MockAdapter, \
         patch("app.workers.stages.parse._run_serve_adapter", new_callable=AsyncMock) as mock_serve:
        mock_instance = MagicMock()
        mock_instance.parse = AsyncMock(return_value=mock_parsed)
        MockAdapter.return_value = mock_instance

        result = await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="t1",
            settings=settings,
            cfg=cfg,
        )

    MockAdapter.assert_called_once()
    mock_serve.assert_not_awaited()
    assert result is mock_parsed


# ---------------------------------------------------------------------------
# 10.8 — parse stage parser="pdfminer" → _extract_text() called directly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_pdfminer_calls_extract_text() -> None:
    from app.workers.stages import parse as parse_module

    cfg = _make_cfg(parser="pdfminer")
    settings = _make_settings(docling_serve_url=None)

    with patch("app.workers.stages.parse._extract_text", return_value="plain text") as mock_extract, \
         patch("app.workers.stages.parse.DoclingParserAdapter", autospec=True) as MockAdapter, \
         patch("app.workers.stages.parse._run_serve_adapter", new_callable=AsyncMock) as mock_serve:

        result = await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="t1",
            settings=settings,
            cfg=cfg,
        )

    mock_extract.assert_called_once()
    MockAdapter.assert_not_called()
    mock_serve.assert_not_awaited()
    assert result == "plain text"


# ---------------------------------------------------------------------------
# 10.9 — parse stage parser="auto" → existing chain preserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_auto_uses_existing_chain() -> None:
    from app.workers.stages import parse as parse_module

    mock_parsed = MagicMock(spec=ParsedDocument)
    mock_parsed.elements = []
    mock_parsed.quality = MagicMock()

    cfg = _make_cfg(parser="auto")
    # With DOCLING_SERVE_URL set, auto should use serve adapter
    settings = _make_settings(docling_serve_url="http://auto-serve:5001")

    with patch("app.workers.stages.parse._run_serve_adapter", new_callable=AsyncMock) as mock_serve:
        mock_serve.return_value = mock_parsed
        parse_module._http_client = None

        result = await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id="t1",
            settings=settings,
            cfg=cfg,
        )

    mock_serve.assert_awaited_once()
    assert result is mock_parsed


# ---------------------------------------------------------------------------
# Domain defaults
# ---------------------------------------------------------------------------

def test_ingestion_config_defaults_include_parser_fields() -> None:
    assert INGESTION_CONFIG_DEFAULTS.parser == "auto"
    assert INGESTION_CONFIG_DEFAULTS.docling_serve_url is None
