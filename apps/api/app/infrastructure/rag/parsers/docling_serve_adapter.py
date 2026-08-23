"""Docling-serve HTTP adapter for document parsing.

Delegates document conversion to a remote ``docling-serve`` instance via its
async REST API instead of running docling in-process. Implements the
``DocumentParser`` port — drop-in replacement for ``DoclingParserAdapter``
when ``DOCLING_SERVE_URL`` is configured.

API flow:
  POST /v1/convert/file/async  → task_id
  GET  /v1/status/poll/{id}    → poll until success | failed | timeout
  GET  /v1/result/{id}         → md_content + confidence
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

import httpx

from app.domain.errors import DomainError
from app.domain.rag.adapter_ports import assert_tenant_scope
from app.domain.rag.elements import (
    SUPPORTED_MIME_TYPES,
    DocumentElement,
    ElementType,
    ParsedDocument,
    ParserProfile,
    ParserQualitySummary,
)
from app.domain.tenant_context import TenantContext

logger = logging.getLogger(__name__)

# MIME type → file extension for multipart upload
_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "application/markdown": ".md",
    "text/plain": ".txt",
}


def _deterministic_element_id(*, profile_version: str, index: int, text: str) -> str:
    """Compute a stable element ID from profile version, index, and text."""
    raw = f"{profile_version}:{index}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class DoclingServeAdapter:
    """Document parser adapter backed by a remote docling-serve instance.

    Accepts the same ``DocumentParser`` port contract as ``DoclingParserAdapter``.
    The caller (parse stage) owns the ``httpx.AsyncClient`` lifecycle and passes
    it in at construction time — the adapter never opens or closes the client.
    """

    def __init__(
        self,
        *,
        base_url: str,
        expected_tenant_id: str,
        profile: ParserProfile,
        http_client: httpx.AsyncClient,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._expected_tenant_id = expected_tenant_id
        self._profile = profile
        self._client = http_client
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._api_key = api_key

    def _auth_headers(self) -> dict[str, str]:
        """Return X-Api-Key header dict when api_key is set, else empty."""
        if self._api_key:
            return {"X-Api-Key": self._api_key}
        return {}

    async def parse(
        self,
        *,
        tenant: TenantContext,
        source: bytes,
        mime_type: str,
        parser_profile_id: str,
    ) -> ParsedDocument:
        """Parse source bytes via docling-serve. Returns canonical ParsedDocument."""
        # 1. Tenant scope guard — before any I/O
        assert_tenant_scope(tenant, self._expected_tenant_id)

        # 2. Profile ID guard
        if parser_profile_id != self._profile.id:
            raise DomainError(
                "PARSER_PROFILE_MISMATCH",
                "Parser profile id does not match the adapter profile",
                400,
            )

        # 3. MIME type guard — before any I/O
        if mime_type not in SUPPORTED_MIME_TYPES:
            raise DomainError(
                "UNSUPPORTED_MIME_TYPE",
                f"MIME type '{mime_type}' is not supported. Supported: {sorted(SUPPORTED_MIME_TYPES)}",
                400,
            )

        # 4. Submit → poll → fetch → map
        task_id = await self._submit(source, mime_type)
        await self._poll(task_id)
        result = await self._fetch_result(task_id)
        return self._map_to_parsed_document(result)

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    async def _submit(self, source: bytes, mime_type: str) -> str:
        """POST file bytes to /v1/convert/file/async. Returns task_id."""
        ext = _MIME_TO_EXT.get(mime_type, ".bin")
        url = f"{self._base_url}/v1/convert/file/async"
        try:
            response = await self._client.post(
                url,
                files={"files": (f"document{ext}", source, mime_type)},
                headers=self._auth_headers(),
            )
        except httpx.RequestError as exc:
            raise DomainError(
                "DOCLING_SERVE_SUBMIT_ERROR",
                f"Failed to connect to docling-serve at {url}: {exc}",
                502,
                {"url": url, "error": str(exc)},
            ) from exc

        if response.status_code >= 300:
            raise DomainError(
                "DOCLING_SERVE_SUBMIT_ERROR",
                f"docling-serve returned HTTP {response.status_code} on submit",
                502,
                {"status": response.status_code, "body": response.text[:500]},
            )

        data = response.json()
        task_id: str = data["task_id"]
        logger.debug("[docling-serve] submitted task_id=%s mime=%s bytes=%d", task_id, mime_type, len(source))
        return task_id

    async def _poll(self, task_id: str) -> None:
        """Poll /v1/status/poll/{task_id} until terminal status or timeout."""
        url = f"{self._base_url}/v1/status/poll/{task_id}"
        deadline = time.monotonic() + self._timeout
        first = True

        while True:
            if not first:
                await asyncio.sleep(self._poll_interval)
            first = False

            elapsed = time.monotonic() - (deadline - self._timeout)
            if time.monotonic() > deadline:
                raise DomainError(
                    "DOCLING_SERVE_TIMEOUT",
                    f"docling-serve task {task_id!r} did not complete within {self._timeout}s",
                    504,
                    {"task_id": task_id, "elapsed_seconds": round(elapsed, 1), "timeout_seconds": self._timeout},
                )

            try:
                response = await self._client.get(url, headers=self._auth_headers())
            except httpx.RequestError as exc:
                raise DomainError(
                    "DOCLING_SERVE_POLL_ERROR",
                    f"Failed to poll docling-serve task {task_id!r}: {exc}",
                    502,
                    {"task_id": task_id, "error": str(exc)},
                ) from exc

            if response.status_code >= 300:
                raise DomainError(
                    "DOCLING_SERVE_POLL_ERROR",
                    f"docling-serve returned HTTP {response.status_code} while polling {task_id!r}",
                    502,
                    {"task_id": task_id, "status": response.status_code, "body": response.text[:500]},
                )

            data = response.json()
            status: str = data.get("task_status", "")
            logger.debug("[docling-serve] poll task_id=%s status=%s elapsed=%.1fs", task_id, status, elapsed)

            if status == "success":
                return
            if status == "failed":
                raise DomainError(
                    "DOCLING_SERVE_TASK_FAILED",
                    f"docling-serve task {task_id!r} failed",
                    502,
                    {"task_id": task_id, "error_message": data.get("error_message") or data.get("failure")},
                )
            # pending | started → continue polling

    async def _fetch_result(self, task_id: str) -> dict[str, Any]:
        """GET /v1/result/{task_id}. Returns raw result dict."""
        url = f"{self._base_url}/v1/result/{task_id}"
        try:
            response = await self._client.get(url, headers=self._auth_headers())
        except httpx.RequestError as exc:
            raise DomainError(
                "DOCLING_SERVE_RESULT_ERROR",
                f"Failed to fetch result for task {task_id!r}: {exc}",
                502,
                {"task_id": task_id, "error": str(exc)},
            ) from exc

        if response.status_code >= 300:
            raise DomainError(
                "DOCLING_SERVE_RESULT_ERROR",
                f"docling-serve returned HTTP {response.status_code} fetching result for {task_id!r}",
                502,
                {"task_id": task_id, "status": response.status_code, "body": response.text[:500]},
            )

        return response.json()  # type: ignore[return-value]

    def _map_to_parsed_document(self, result: dict[str, Any]) -> ParsedDocument:
        """Map docling-serve result JSON to canonical ParsedDocument."""
        doc = result.get("document") or {}
        md_content: str = doc.get("md_content") or ""
        confidence: dict[str, Any] = result.get("confidence") or {}

        # Map non-empty lines → DocumentElement
        elements: list[DocumentElement] = []
        for idx, line in enumerate(md_content.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue
            elem_id = _deterministic_element_id(
                profile_version=self._profile.version,
                index=idx,
                text=stripped,
            )
            elements.append(
                DocumentElement(
                    id=elem_id,
                    type=ElementType.NARRATIVE,
                    text=stripped,
                    page=None,
                    bounding_box=None,
                    hierarchy_path=(),
                    source_offsets=None,
                    structured_payload=None,
                    extraction_confidence=confidence.get("mean_score"),
                )
            )

        # Build ParserQualitySummary from confidence object
        total = len(elements)
        non_empty = sum(1 for e in elements if e.text.strip())
        empty_ratio = 1.0 - (non_empty / total) if total else 0.0

        quality = ParserQualitySummary(
            element_count=total,
            text_coverage=float(confidence.get("parse_score") or 0.0),
            empty_element_ratio=empty_ratio,
            page_coverage=confidence.get("layout_score"),
            aggregate_confidence=confidence.get("mean_score"),
        )

        logger.debug(
            "[docling-serve] mapped %d elements text_coverage=%.3f aggregate_confidence=%s",
            total,
            quality.text_coverage,
            quality.aggregate_confidence,
        )
        return ParsedDocument(elements=elements, quality=quality)
