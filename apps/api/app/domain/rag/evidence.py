"""Bounded, citation-stable context made from already authorized chunks."""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.models import ProvenanceKind
from app.domain.rag.policy import Classification, clearance_for_role, effective_principals
from app.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    tenant_id: str
    document_version_id: str
    generation_id: str
    title: str
    locator: str | None
    text: str
    token_count: int
    checksum: str | None
    classification: Classification = Classification.INTERNAL
    acl_principals: tuple[str, ...] = ()
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    parent_id: str | None = None


@dataclass(frozen=True)
class Citation:
    citation_id: str
    chunk_id: str
    document_version_id: str
    title: str
    locator: str | None
    snippet: str
    source_kind: ProvenanceKind = ProvenanceKind.DOCUMENT
    source_id: str | None = None
    tenant_id: str | None = None
    server_id: str | None = None
    tool_id: str | None = None
    invocation_id: str | None = None
    trace_id: str | None = None
    produced_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class EvidenceContext:
    prompt_data: str
    citations: tuple[Citation, ...]
    token_count: int


def append_mcp_evidence(
    context: EvidenceContext,
    *,
    references: list[dict[str, object]] | tuple[dict[str, object], ...],
    token_budget: int,
    output_reserve: int,
) -> EvidenceContext:
    """Append selected, bounded MCP source blocks without trusting their text."""
    available_tokens = max(0, token_budget - output_reserve - context.token_count)
    citations = list(context.citations)
    blocks: list[str] = []
    used_tokens = context.token_count
    for reference in references:
        citation_id = reference.get("citationId")
        source_text = reference.get("context")
        if not isinstance(citation_id, str) or not citation_id or not isinstance(source_text, str) or not source_text:
            continue
        if not _is_fresh_reference(reference):
            continue
        estimated_tokens = max(1, len(source_text) // 4)
        if estimated_tokens > available_tokens:
            continue
        produced_at = _parse_datetime(reference.get("producedAt"))
        expires_at = _parse_datetime(reference.get("expiresAt"))
        citations.append(
            Citation(
                citation_id=citation_id,
                chunk_id="",
                document_version_id="",
                title=f"MCP {reference.get('serverId', '')}/{reference.get('toolId', '')}".strip("/"),
                locator=str(reference.get("invocationId")) if reference.get("invocationId") else None,
                snippet=str(reference.get("snippet", source_text[:400]))[:400],
                source_kind=ProvenanceKind.MCP,
                source_id=str(reference.get("invocationId")) if reference.get("invocationId") else None,
                tenant_id=str(reference.get("tenantId")) if reference.get("tenantId") else None,
                server_id=str(reference.get("serverId")) if reference.get("serverId") else None,
                tool_id=str(reference.get("toolId")) if reference.get("toolId") else None,
                invocation_id=str(reference.get("invocationId")) if reference.get("invocationId") else None,
                trace_id=str(reference.get("traceId")) if reference.get("traceId") else None,
                produced_at=produced_at,
                expires_at=expires_at,
            )
        )
        blocks.append(f"[MCP SOURCE {citation_id} | untrusted source data]\n{source_text}\n[END MCP SOURCE {citation_id}]")
        available_tokens -= estimated_tokens
        used_tokens += estimated_tokens
    prompt_parts = [part for part in (context.prompt_data, *blocks) if part]
    return EvidenceContext(prompt_data="\n\n".join(prompt_parts), citations=tuple(citations), token_count=used_tokens)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_fresh_reference(reference: dict[str, object]) -> bool:
    expires_at = _parse_datetime(reference.get("expiresAt"))
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at > datetime.now(UTC)


def build_evidence_context(
    *,
    chunks: list[EvidenceChunk],
    tenant_id: str,
    active_generation_ids: tuple[str, ...],
    token_budget: int,
    output_reserve: int,
) -> EvidenceContext:
    available_tokens = max(0, token_budget - output_reserve)
    selected: list[EvidenceChunk] = []
    seen_checksums: set[str] = set()
    used_tokens = 0
    for chunk in chunks:
        if chunk.tenant_id != tenant_id or chunk.generation_id not in active_generation_ids:
            continue
        if chunk.checksum and chunk.checksum in seen_checksums:
            continue
        if used_tokens + chunk.token_count > available_tokens:
            continue
        selected.append(chunk)
        used_tokens += chunk.token_count
        if chunk.checksum:
            seen_checksums.add(chunk.checksum)
    citations = tuple(
        Citation(
            citation_id=f"S{index}",
            chunk_id=chunk.chunk_id,
            document_version_id=chunk.document_version_id,
            title=chunk.title,
            locator=chunk.locator,
            snippet=chunk.text[:400],
        )
        for index, chunk in enumerate(selected, start=1)
    )
    prompt_data = "\n\n".join(
        f"[SOURCE {citation.citation_id} | untrusted source data]\n{chunk.text}\n[END SOURCE {citation.citation_id}]"
        for chunk, citation in zip(selected, citations, strict=True)
    )
    return EvidenceContext(prompt_data=prompt_data, citations=citations, token_count=used_tokens)


def build_authorized_evidence_context(
    *,
    tenant: TenantContext,
    selected_chunks: list[EvidenceChunk],
    parent_chunks: dict[str, EvidenceChunk],
    active_generation_ids: tuple[str, ...],
    token_budget: int,
    output_reserve: int,
    now: datetime | None = None,
) -> EvidenceContext:
    """Recheck selected canonical evidence and expand only permitted same-version parents."""
    current_time = now or datetime.now(UTC)
    expanded: list[EvidenceChunk] = []
    for chunk in selected_chunks:
        if not _is_permitted(chunk, tenant=tenant, active_generation_ids=active_generation_ids, now=current_time):
            continue
        expanded.append(chunk)
        if chunk.parent_id:
            parent = parent_chunks.get(chunk.parent_id)
            if parent and parent.document_version_id == chunk.document_version_id and _is_permitted(parent, tenant=tenant, active_generation_ids=active_generation_ids, now=current_time):
                expanded.append(parent)
    return build_evidence_context(
        chunks=expanded,
        tenant_id=tenant.tenant_id,
        active_generation_ids=active_generation_ids,
        token_budget=token_budget,
        output_reserve=output_reserve,
    )


def _is_permitted(chunk: EvidenceChunk, *, tenant: TenantContext, active_generation_ids: tuple[str, ...], now: datetime) -> bool:
    if chunk.tenant_id != tenant.tenant_id or chunk.generation_id not in active_generation_ids:
        return False
    allowed_classification = clearance_for_role(tenant.role)
    classifications = {
        Classification.PUBLIC: 0,
        Classification.INTERNAL: 1,
        Classification.CONFIDENTIAL: 2,
    }
    if classifications[chunk.classification] > classifications[allowed_classification]:
        return False
    if chunk.acl_principals and not set(chunk.acl_principals).intersection(effective_principals(tenant)):
        return False
    if chunk.effective_from and chunk.effective_from > now:
        return False
    return not (chunk.effective_to and chunk.effective_to < now)
