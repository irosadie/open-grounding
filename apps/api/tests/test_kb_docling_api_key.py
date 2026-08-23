"""Unit tests for kb-docling-api-key change.

Covers tasks 11.1–11.8:
- 11.1 upsert_config with key → encrypted, not plain text
- 11.2 upsert_config with key=None → clears enc
- 11.3 upsert_config with key=_UNSET → keeps existing
- 11.4 get_api_key_decrypted → returns original plain-text
- 11.5 DoclingServeAdapter with api_key → X-Api-Key header on all requests
- 11.6 DoclingServeAdapter with api_key=None → no X-Api-Key header
- 11.7 IngestionConfigResult.docling_serve_api_key_set is True when enc key set
- 11.8 parse stage passes decrypted key to _run_serve_adapter
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call

import httpx
import pytest

from app.domain.rag.catalog import INGESTION_CONFIG_DEFAULTS, IngestionConfig
from app.domain.rag.elements import ParsedDocument
from app.domain.tenant_context import TenantContext

_TENANT_ID = "tenant-abc"
_TENANT = TenantContext(tenant_id=_TENANT_ID, membership_id=_TENANT_ID, user_id=_TENANT_ID)


def _make_cfg(**kwargs) -> IngestionConfig:
    base = {
        "id": "cfg-1",
        "tenant_id": _TENANT_ID,
        "knowledge_base_id": "kb-1",
        "min_text_coverage": 0.3,
        "max_invalid_char_ratio": 0.1,
        "min_aggregate_confidence": 0.5,
        "min_page_coverage": 0.5,
        "auto_review": False,
        "parser": "docling_serve",
        "docling_serve_url": "http://serve:5001",
        "docling_serve_api_key_enc": None,
        "created_at": INGESTION_CONFIG_DEFAULTS.created_at,
        "updated_at": INGESTION_CONFIG_DEFAULTS.updated_at,
    }
    base.update(kwargs)
    return IngestionConfig(**base)


# ---------------------------------------------------------------------------
# 11.1 — upsert_config with key → encrypted, not plain text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_encrypts_api_key() -> None:
    from app.application.ingestion_config_service import IngestionConfigService
    from app.core.settings import Settings

    settings = Settings(secret_key="test-secret-key-32-chars-padding!")

    mock_session = AsyncMock()
    svc = IngestionConfigService(mock_session)
    svc._kb_repo = MagicMock()
    svc._kb_repo.find_by_id = AsyncMock(return_value=MagicMock())
    svc._repo = MagicMock()
    svc._repo.get_by_kb = AsyncMock(return_value=None)

    captured_enc: list[str] = []

    async def fake_upsert(**kwargs):
        captured_enc.append(kwargs.get("docling_serve_api_key_enc", ""))
        return _make_cfg(docling_serve_api_key_enc=kwargs.get("docling_serve_api_key_enc"))

    svc._repo.upsert = fake_upsert

    result = await svc.upsert_config(
        tenant=_TENANT,
        knowledge_base_id="kb-1",
        min_text_coverage=0.3,
        max_invalid_char_ratio=0.1,
        min_aggregate_confidence=0.5,
        min_page_coverage=0.5,
        auto_review=False,
        parser="docling_serve",
        docling_serve_url="http://serve:5001",
        docling_serve_api_key="my-secret-key",
        settings=settings,
    )

    assert captured_enc[0] is not None
    assert captured_enc[0] != "my-secret-key"  # must be encrypted
    assert result.docling_serve_api_key_set is True


# ---------------------------------------------------------------------------
# 11.2 — upsert_config with key=None → clears enc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_clears_api_key_when_none() -> None:
    from app.application.ingestion_config_service import IngestionConfigService
    from app.core.settings import Settings

    settings = Settings()
    mock_session = AsyncMock()
    svc = IngestionConfigService(mock_session)
    svc._kb_repo = MagicMock()
    svc._kb_repo.find_by_id = AsyncMock(return_value=MagicMock())

    captured_enc: list = []

    async def fake_upsert(**kwargs):
        captured_enc.append(kwargs.get("docling_serve_api_key_enc"))
        return _make_cfg(docling_serve_api_key_enc=None)

    svc._repo = MagicMock()
    svc._repo.get_by_kb = AsyncMock(return_value=None)
    svc._repo.upsert = fake_upsert

    await svc.upsert_config(
        tenant=_TENANT,
        knowledge_base_id="kb-1",
        min_text_coverage=0.3,
        max_invalid_char_ratio=0.1,
        min_aggregate_confidence=0.5,
        min_page_coverage=0.5,
        auto_review=False,
        parser="docling_serve",
        docling_serve_url="http://serve:5001",
        docling_serve_api_key=None,
        settings=settings,
    )

    assert captured_enc[0] is None


# ---------------------------------------------------------------------------
# 11.3 — upsert_config with key=_UNSET → keeps existing enc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_keeps_existing_key_when_unset() -> None:
    from app.application.ingestion_config_service import IngestionConfigService, _UNSET
    from app.core.settings import Settings

    settings = Settings()
    existing_enc = "existing-encrypted-value"
    mock_session = AsyncMock()
    svc = IngestionConfigService(mock_session)
    svc._kb_repo = MagicMock()
    svc._kb_repo.find_by_id = AsyncMock(return_value=MagicMock())

    captured_enc: list = []

    async def fake_upsert(**kwargs):
        captured_enc.append(kwargs.get("docling_serve_api_key_enc"))
        return _make_cfg(docling_serve_api_key_enc=existing_enc)

    svc._repo = MagicMock()
    svc._repo.get_by_kb = AsyncMock(return_value=_make_cfg(docling_serve_api_key_enc=existing_enc))
    svc._repo.upsert = fake_upsert

    await svc.upsert_config(
        tenant=_TENANT,
        knowledge_base_id="kb-1",
        min_text_coverage=0.3,
        max_invalid_char_ratio=0.1,
        min_aggregate_confidence=0.5,
        min_page_coverage=0.5,
        auto_review=False,
        parser="docling_serve",
        docling_serve_url="http://serve:5001",
        docling_serve_api_key=_UNSET,
        settings=settings,
    )

    assert captured_enc[0] == existing_enc


# ---------------------------------------------------------------------------
# 11.4 — get_api_key_decrypted returns original plain-text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_api_key_decrypted_returns_plaintext() -> None:
    from app.application.ingestion_config_service import IngestionConfigService
    from app.core.settings import Settings
    from app.infrastructure.crypto import encrypt, get_encryption_key

    settings = Settings(secret_key="test-secret-key-32-chars-padding!")
    plain_key = "my-docling-api-key"
    enc_key = get_encryption_key(settings)
    encrypted = encrypt(plain_key, enc_key)

    mock_session = AsyncMock()
    svc = IngestionConfigService(mock_session)
    svc._repo = MagicMock()
    svc._repo.get_by_kb = AsyncMock(return_value=_make_cfg(docling_serve_api_key_enc=encrypted))

    result = await svc.get_api_key_decrypted(
        tenant=_TENANT,
        knowledge_base_id="kb-1",
        settings=settings,
    )

    assert result == plain_key


# ---------------------------------------------------------------------------
# 11.5 — DoclingServeAdapter with api_key → X-Api-Key on all requests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapter_injects_api_key_header() -> None:
    from app.domain.rag.elements import ParserProfile
    from app.infrastructure.rag.parsers.docling_serve_adapter import DoclingServeAdapter

    profile = ParserProfile(id="default-v1", pipeline="standard", model="layout", ocr_enabled=False, version="1")
    client = MagicMock(spec=httpx.AsyncClient)

    submit_resp = MagicMock(); submit_resp.status_code = 200; submit_resp.json.return_value = {"task_id": "t1"}
    poll_resp = MagicMock(); poll_resp.status_code = 200; poll_resp.json.return_value = {"task_status": "success"}
    result_resp = MagicMock(); result_resp.status_code = 200; result_resp.json.return_value = {
        "document": {"md_content": "hello"}, "confidence": {"mean_score": 0.9, "parse_score": 1.0, "layout_score": 0.9}
    }
    client.post = AsyncMock(return_value=submit_resp)
    client.get = AsyncMock(side_effect=[poll_resp, result_resp])

    adapter = DoclingServeAdapter(
        base_url="http://serve:5001",
        expected_tenant_id=_TENANT_ID,
        profile=profile,
        http_client=client,
        poll_interval=0.01,
        timeout=5.0,
        api_key="my-key",
    )

    await adapter.parse(
        tenant=_TENANT,
        source=b"data",
        mime_type="application/pdf",
        parser_profile_id="default-v1",
    )

    # All calls should have X-Api-Key header
    post_headers = client.post.call_args.kwargs.get("headers", {})
    assert post_headers.get("X-Api-Key") == "my-key"

    for get_call in client.get.call_args_list:
        get_headers = get_call.kwargs.get("headers", {})
        assert get_headers.get("X-Api-Key") == "my-key"


# ---------------------------------------------------------------------------
# 11.6 — DoclingServeAdapter with api_key=None → no X-Api-Key header
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapter_no_header_when_api_key_none() -> None:
    from app.domain.rag.elements import ParserProfile
    from app.infrastructure.rag.parsers.docling_serve_adapter import DoclingServeAdapter

    profile = ParserProfile(id="default-v1", pipeline="standard", model="layout", ocr_enabled=False, version="1")
    client = MagicMock(spec=httpx.AsyncClient)

    submit_resp = MagicMock(); submit_resp.status_code = 200; submit_resp.json.return_value = {"task_id": "t1"}
    poll_resp = MagicMock(); poll_resp.status_code = 200; poll_resp.json.return_value = {"task_status": "success"}
    result_resp = MagicMock(); result_resp.status_code = 200; result_resp.json.return_value = {
        "document": {"md_content": "hello"}, "confidence": {}
    }
    client.post = AsyncMock(return_value=submit_resp)
    client.get = AsyncMock(side_effect=[poll_resp, result_resp])

    adapter = DoclingServeAdapter(
        base_url="http://serve:5001",
        expected_tenant_id=_TENANT_ID,
        profile=profile,
        http_client=client,
        poll_interval=0.01,
        timeout=5.0,
        api_key=None,
    )

    await adapter.parse(
        tenant=_TENANT,
        source=b"data",
        mime_type="application/pdf",
        parser_profile_id="default-v1",
    )

    post_headers = client.post.call_args.kwargs.get("headers", {})
    assert "X-Api-Key" not in post_headers


# ---------------------------------------------------------------------------
# 11.7 — IngestionConfigResult.docling_serve_api_key_set
# ---------------------------------------------------------------------------

def test_ingestion_config_result_api_key_set_true() -> None:
    from app.application.ingestion_config_service import _to_result
    cfg = _make_cfg(docling_serve_api_key_enc="some-encrypted-value")
    result = _to_result(cfg)
    assert result.docling_serve_api_key_set is True


def test_ingestion_config_result_api_key_set_false() -> None:
    from app.application.ingestion_config_service import _to_result
    cfg = _make_cfg(docling_serve_api_key_enc=None)
    result = _to_result(cfg)
    assert result.docling_serve_api_key_set is False


# ---------------------------------------------------------------------------
# 11.8 — parse stage passes decrypted key to _run_serve_adapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_passes_decrypted_key_to_serve_adapter() -> None:
    from app.core.settings import Settings
    from app.infrastructure.crypto import encrypt, get_encryption_key
    from app.workers.stages import parse as parse_module

    settings = Settings(
        secret_key="test-secret-key-32-chars-padding!",
        docling_serve_url=None,
    )
    plain_key = "my-docling-api-key"
    enc_key = get_encryption_key(settings)
    encrypted = encrypt(plain_key, enc_key)

    cfg = _make_cfg(
        parser="docling_serve",
        docling_serve_url="http://serve:5001",
        docling_serve_api_key_enc=encrypted,
    )

    mock_parsed = MagicMock(spec=ParsedDocument)
    mock_parsed.elements = []
    mock_parsed.quality = MagicMock()

    with patch("app.workers.stages.parse._run_serve_adapter", new_callable=AsyncMock) as mock_serve:
        mock_serve.return_value = mock_parsed
        parse_module._http_client = None

        await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id=_TENANT_ID,
            settings=settings,
            cfg=cfg,
            docling_api_key=plain_key,
        )

    call_kwargs = mock_serve.call_args.kwargs
    assert call_kwargs["api_key"] == plain_key
