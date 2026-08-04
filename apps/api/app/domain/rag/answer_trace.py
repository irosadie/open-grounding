"""Safe, tenant-scoped answer trace entities without source text or reasoning."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AnswerRun:
    id: str
    tenant_id: str
    trace_id: str
    conversation_id: str | None
    original_query: str
    standalone_query: str | None
    route: str
    evidence_level: str
    profile_snapshot: dict[str, object]
    limitations: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class AnswerCitation:
    id: str
    tenant_id: str
    answer_run_id: str
    citation_id: str
    chunk_id: str
    document_version_id: str
    locator: str | None
    created_at: datetime


@dataclass(frozen=True)
class AnswerFeedback:
    id: str
    tenant_id: str
    answer_run_id: str
    user_id: str
    rating: int | None
    comment: str | None
    created_at: datetime
