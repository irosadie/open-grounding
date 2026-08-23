"""Unit tests for DoclingServeAdapter and parse stage serve integration.

Covers tasks 4.1–4.15:
- 4.1  Happy path: returns ParsedDocument with correct elements + quality
- 4.2  Timeout: DomainError(DOCLING_SERVE_TIMEOUT)
- 4.3  Failed task: DomainError(DOCLING_SERVE_TASK_FAILED)
- 4.4  Submit HTTP error: DomainError(DOCLING_SERVE_SUBMIT_ERROR)
- 4.5  Poll HTTP error: DomainError(DOCLING_SERVE_POLL_ERROR)
- 4.6  Result fetch HTTP error: DomainError(DOCLING_SERVE_RESULT_ERROR)
- 4.7  Tenant mismatch: raises before any HTTP call
- 4.8  Unsupported MIME type: raises before any HTTP call
- 4.9  Empty md_content: ParsedDocument with zero elements, no raise
- 4.10 Absent confidence: ParserQualitySummary with None/0.0 defaults
- 4.11 Parse stage routing: DOCLING_SERVE_URL set → serve adapter used
- 4.12 Parse stage routing: DOCLING_SERVE_URL absent → in-process path unchanged
- 4.13 Settings validator: invalid URL → ValueError
- 4.14 Settings validator: timeout=0 → ValueError
- 4.15 Shared client: _get_http_client() returns same instance
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.domain.errors import DomainError
from app.domain.rag.catalog import INGESTION_CONFIG_DEFAULTS
from app.domain.rag.elements import ParsedDocument, ParserProfile
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag.parsers.docling_serve_adapter import DoclingServeAdapter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PROFILE = ParserProfile(
    id="default-v1",
    pipeline="standard",
    model="layout",
    ocr_enabled=False,
    version="1",
)

_TENANT_ID = "tenant-abc"
_TENANT = TenantContext(tenant_id=_TENANT_ID, membership_id=_TENANT_ID, user_id=_TENANT_ID)

_RESULT_PAYLOAD = {
    "document": {
        "md_content": "## Heading\n\nFirst paragraph\n\nSecond paragraph",
    },
    "status": "success",
    "confidence": {
        "parse_score": 1.0,
        "layout_score": 0.92,
        "mean_score": 0.96,
    },
}


def _make_adapter(
    http_client: httpx.AsyncClient,
    poll_interval: float = 0.01,
    timeout: float = 5.0,
) -> DoclingServeAdapter:
    return DoclingServeAdapter(
        base_url="http://localhost:5001",
        expected_tenant_id=_TENANT_ID,
        profile=_PROFILE,
        http_client=http_client,
        poll_interval=poll_interval,
        timeout=timeout,
    )


def _mock_response(status_code: int = 200, json_data: object = None, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# 4.1 — Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_returns_parsed_document() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(200, {"task_id": "t1"}))
    client.get = AsyncMock(side_effect=[
        _mock_response(200, {"task_status": "success"}),
        _mock_response(200, _RESULT_PAYLOAD),
    ])

    adapter = _make_adapter(client)
    result = await adapter.parse(
        tenant=_TENANT,
        source=b"%PDF-1.4 fake",
        mime_type="application/pdf",
        parser_profile_id="default-v1",
    )

    assert isinstance(result, ParsedDocument)
    assert len(result.elements) == 3  # "## Heading", "First paragraph", "Second paragraph"
    assert result.elements[0].text == "## Heading"
    assert result.elements[1].text == "First paragraph"
    assert result.quality.aggregate_confidence == pytest.approx(0.96)
    assert result.quality.text_coverage == pytest.approx(1.0)
    assert result.quality.page_coverage == pytest.approx(0.92)
    assert result.quality.element_count == 3


# ---------------------------------------------------------------------------
# 4.2 — Timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_raises_domain_error() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(200, {"task_id": "t-timeout"}))
    # Poll always returns "started"
    client.get = AsyncMock(return_value=_mock_response(200, {"task_status": "started"}))

    adapter = _make_adapter(client, poll_interval=0.01, timeout=0.05)
    with pytest.raises(DomainError) as exc_info:
        await adapter.parse(
            tenant=_TENANT,
            source=b"data",
            mime_type="application/pdf",
            parser_profile_id="default-v1",
        )

    err = exc_info.value
    assert err.code == "DOCLING_SERVE_TIMEOUT"
    assert err.details is not None
    assert err.details["task_id"] == "t-timeout"
    assert "elapsed_seconds" in err.details


# ---------------------------------------------------------------------------
# 4.3 — Failed task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_task_raises_domain_error() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(200, {"task_id": "t-fail"}))
    client.get = AsyncMock(return_value=_mock_response(
        200, {"task_status": "failed", "error_message": "conversion error", "failure": None}
    ))

    adapter = _make_adapter(client)
    with pytest.raises(DomainError) as exc_info:
        await adapter.parse(
            tenant=_TENANT,
            source=b"data",
            mime_type="application/pdf",
            parser_profile_id="default-v1",
        )

    err = exc_info.value
    assert err.code == "DOCLING_SERVE_TASK_FAILED"
    assert err.details["task_id"] == "t-fail"
    assert err.details["error_message"] == "conversion error"


# ---------------------------------------------------------------------------
# 4.4 — Submit HTTP error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_http_error_raises_domain_error() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(500, text="internal error"))

    adapter = _make_adapter(client)
    with pytest.raises(DomainError) as exc_info:
        await adapter.parse(
            tenant=_TENANT,
            source=b"data",
            mime_type="application/pdf",
            parser_profile_id="default-v1",
        )

    err = exc_info.value
    assert err.code == "DOCLING_SERVE_SUBMIT_ERROR"
    assert err.details["status"] == 500


# ---------------------------------------------------------------------------
# 4.5 — Poll HTTP error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_http_error_raises_domain_error() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(200, {"task_id": "t-poll-err"}))
    client.get = AsyncMock(return_value=_mock_response(503, text="unavailable"))

    adapter = _make_adapter(client)
    with pytest.raises(DomainError) as exc_info:
        await adapter.parse(
            tenant=_TENANT,
            source=b"data",
            mime_type="application/pdf",
            parser_profile_id="default-v1",
        )

    err = exc_info.value
    assert err.code == "DOCLING_SERVE_POLL_ERROR"
    assert err.details["task_id"] == "t-poll-err"
    assert err.details["status"] == 503


# ---------------------------------------------------------------------------
# 4.6 — Result fetch HTTP error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_fetch_http_error_raises_domain_error() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(200, {"task_id": "t-result-err"}))
    client.get = AsyncMock(side_effect=[
        _mock_response(200, {"task_status": "success"}),
        _mock_response(404, text="not found"),
    ])

    adapter = _make_adapter(client)
    with pytest.raises(DomainError) as exc_info:
        await adapter.parse(
            tenant=_TENANT,
            source=b"data",
            mime_type="application/pdf",
            parser_profile_id="default-v1",
        )

    err = exc_info.value
    assert err.code == "DOCLING_SERVE_RESULT_ERROR"
    assert err.details["task_id"] == "t-result-err"
    assert err.details["status"] == 404


# ---------------------------------------------------------------------------
# 4.7 — Tenant mismatch: no HTTP call made
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_mismatch_raises_before_http_call() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock()

    adapter = _make_adapter(client)
    wrong_tenant = TenantContext(tenant_id="other-tenant", membership_id="other-tenant", user_id="other-tenant")

    with pytest.raises(DomainError) as exc_info:
        await adapter.parse(
            tenant=wrong_tenant,
            source=b"data",
            mime_type="application/pdf",
            parser_profile_id="default-v1",
        )

    assert exc_info.value.code == "TENANT_SCOPE_MISMATCH"
    client.post.assert_not_called()


# ---------------------------------------------------------------------------
# 4.8 — Unsupported MIME type: no HTTP call made
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsupported_mime_raises_before_http_call() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock()

    adapter = _make_adapter(client)
    with pytest.raises(DomainError) as exc_info:
        await adapter.parse(
            tenant=_TENANT,
            source=b"data",
            mime_type="application/msword",
            parser_profile_id="default-v1",
        )

    assert exc_info.value.code == "UNSUPPORTED_MIME_TYPE"
    client.post.assert_not_called()


# ---------------------------------------------------------------------------
# 4.9 — Empty md_content: zero elements, no raise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_md_content_returns_zero_elements() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(200, {"task_id": "t-empty"}))
    client.get = AsyncMock(side_effect=[
        _mock_response(200, {"task_status": "success"}),
        _mock_response(200, {
            "document": {"md_content": ""},
            "confidence": {"parse_score": 0.0, "layout_score": None, "mean_score": 0.0},
        }),
    ])

    adapter = _make_adapter(client)
    result = await adapter.parse(
        tenant=_TENANT,
        source=b"data",
        mime_type="application/pdf",
        parser_profile_id="default-v1",
    )

    assert isinstance(result, ParsedDocument)
    assert len(result.elements) == 0
    assert result.quality.text_coverage == pytest.approx(0.0)
    assert result.quality.element_count == 0


# ---------------------------------------------------------------------------
# 4.10 — Absent confidence: defaults to None/0.0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_absent_confidence_uses_defaults() -> None:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_mock_response(200, {"task_id": "t-noconf"}))
    client.get = AsyncMock(side_effect=[
        _mock_response(200, {"task_status": "success"}),
        _mock_response(200, {
            "document": {"md_content": "Some text"},
        }),
    ])

    adapter = _make_adapter(client)
    result = await adapter.parse(
        tenant=_TENANT,
        source=b"data",
        mime_type="application/pdf",
        parser_profile_id="default-v1",
    )

    assert result.quality.aggregate_confidence is None
    assert result.quality.text_coverage == pytest.approx(0.0)
    assert result.quality.page_coverage is None
    assert len(result.elements) == 1


# ---------------------------------------------------------------------------
# 4.11 — Parse stage routing: DOCLING_SERVE_URL set → serve adapter used
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_uses_serve_adapter_when_url_set() -> None:
    from app.core.settings import Settings
    from app.workers.stages import parse as parse_module

    mock_parsed = MagicMock(spec=ParsedDocument)
    mock_parsed.elements = []
    mock_parsed.quality = MagicMock()

    settings = Settings(
        docling_serve_url="http://localhost:5001",
        docling_serve_timeout_seconds=10.0,
        docling_serve_poll_interval_seconds=0.1,
    )

    # DoclingServeAdapter is imported lazily inside the function — patch at source
    with patch(
        "app.infrastructure.rag.parsers.docling_serve_adapter.DoclingServeAdapter",
        autospec=True,
    ) as MockServe, patch(
        "app.workers.stages.parse.DoclingParserAdapter",
        autospec=True,
    ) as MockInProcess:
        mock_instance = MagicMock()
        mock_instance.parse = AsyncMock(return_value=mock_parsed)
        MockServe.return_value = mock_instance

        # patch the lazy import inside the function
        with patch.dict(
            "sys.modules",
            {"app.infrastructure.rag.parsers.docling_serve_adapter": MagicMock(DoclingServeAdapter=MockServe)},
        ):
            parse_module._http_client = None
            result = await parse_module._parse_with_docling_or_fallback(
                raw_content=b"data",
                mime_type="application/pdf",
                filename="test.pdf",
                tenant_id=_TENANT_ID,
                settings=settings,
                cfg=INGESTION_CONFIG_DEFAULTS,
            )

    MockInProcess.assert_not_called()
    assert result is mock_parsed


# ---------------------------------------------------------------------------
# 4.12 — Parse stage routing: DOCLING_SERVE_URL absent → in-process path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_stage_uses_inprocess_when_url_absent() -> None:
    from app.core.settings import Settings
    from app.workers.stages import parse as parse_module

    mock_parsed = MagicMock(spec=ParsedDocument)
    mock_parsed.elements = []
    mock_parsed.quality = MagicMock()

    settings = Settings(docling_serve_url=None)

    with patch(
        "app.workers.stages.parse.DoclingParserAdapter",
        autospec=True,
    ) as MockInProcess:
        mock_instance = MagicMock()
        mock_instance.parse = AsyncMock(return_value=mock_parsed)
        MockInProcess.return_value = mock_instance

        result = await parse_module._parse_with_docling_or_fallback(
            raw_content=b"data",
            mime_type="application/pdf",
            filename="test.pdf",
            tenant_id=_TENANT_ID,
            settings=settings,
            cfg=INGESTION_CONFIG_DEFAULTS,
        )

    MockInProcess.assert_called_once()
    assert result is mock_parsed


# ---------------------------------------------------------------------------
# 4.13 — Settings validator: invalid URL → ValueError
# ---------------------------------------------------------------------------

def test_settings_invalid_url_raises() -> None:
    from app.core.settings import Settings

    with pytest.raises(Exception):
        Settings(docling_serve_url="not-a-url")


def test_settings_non_http_scheme_raises() -> None:
    from app.core.settings import Settings

    with pytest.raises(Exception):
        Settings(docling_serve_url="ftp://localhost:5001")


# ---------------------------------------------------------------------------
# 4.14 — Settings validator: timeout=0 → ValueError
# ---------------------------------------------------------------------------

def test_settings_zero_timeout_raises() -> None:
    from app.core.settings import Settings

    with pytest.raises(Exception):
        Settings(docling_serve_timeout_seconds=0.0)


def test_settings_negative_poll_interval_raises() -> None:
    from app.core.settings import Settings

    with pytest.raises(Exception):
        Settings(docling_serve_poll_interval_seconds=-1.0)


# ---------------------------------------------------------------------------
# 4.15 — Shared client: _get_http_client() returns same instance
# ---------------------------------------------------------------------------

def test_get_http_client_returns_same_instance() -> None:
    from app.core.settings import Settings
    from app.workers.stages import parse as parse_module

    # Reset module-level client
    parse_module._http_client = None

    settings = Settings()
    client_a = parse_module._get_http_client(settings)
    client_b = parse_module._get_http_client(settings)

    assert client_a is client_b
    assert isinstance(client_a, httpx.AsyncClient)

    # Cleanup
    parse_module._http_client = None
