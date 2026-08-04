"""Bounded, citation-stable context made from already authorized chunks."""

from dataclasses import dataclass
from datetime import UTC, datetime

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


@dataclass(frozen=True)
class EvidenceContext:
    prompt_data: str
    citations: tuple[Citation, ...]
    token_count: int


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
