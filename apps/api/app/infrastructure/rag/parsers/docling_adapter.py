"""Docling-backed document parser adapter.

Implements the ``DocumentParser`` provider port using docling's
``DocumentConverter``. Docling is imported lazily inside ``_convert`` so the
API runs without the heavy ML dependency installed; install with
``uv sync --extra parsing`` to enable real parsing.

Domain and application code never import docling; they consume
``DocumentElement`` records through the ``DocumentParser`` port.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.domain.errors import DomainError
from app.domain.rag.adapter_ports import assert_tenant_scope
from app.domain.rag.elements import SUPPORTED_MIME_TYPES, ParsedDocument, ParserProfile
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag.parsers.mapping import map_docling_to_elements


class DoclingParserAdapter:
    """Concrete ``DocumentParser`` adapter backed by docling.

    Enforces tenant scope and rejects unsupported MIME types before any
    conversion. The profile version seeds deterministic element identifiers.
    """

    def __init__(self, *, expected_tenant_id: str, profile: ParserProfile) -> None:
        self._expected_tenant_id = expected_tenant_id
        self._profile = profile

    async def parse(
        self,
        *,
        tenant: TenantContext,
        source: bytes,
        mime_type: str,
        parser_profile_id: str,
    ) -> ParsedDocument:
        """Parse a source into ordered canonical elements + quality summary."""
        assert_tenant_scope(tenant, self._expected_tenant_id)
        if parser_profile_id != self._profile.id:
            raise DomainError(
                "PARSER_PROFILE_MISMATCH",
                "Parser profile id does not match the adapter profile",
                400,
            )
        if mime_type not in SUPPORTED_MIME_TYPES:
            raise DomainError(
                "UNSUPPORTED_MIME_TYPE",
                f"MIME type '{mime_type}' is not supported in v1. Supported: PDF, Markdown, TXT.",
                400,
            )
        doc = self._convert(source, mime_type)
        return map_docling_to_elements(doc, profile_version=self._profile.version)

    def _convert(self, source: bytes, mime_type: str) -> object:
        """Run docling conversion. Imports docling lazily."""
        try:
            from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
        except ImportError as error:
            raise DomainError(
                "PARSER_NOT_INSTALLED",
                "docling is not installed. Install with: uv sync --extra parsing",
                500,
            ) from error

        suffix = ".pdf" if mime_type == "application/pdf" else (".md" if "markdown" in mime_type else ".txt")
        converter = DocumentConverter()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(source)
            tmp_path = Path(tmp.name)
        try:
            result = converter.convert(tmp_path)
            return result.document
        finally:
            tmp_path.unlink(missing_ok=True)
