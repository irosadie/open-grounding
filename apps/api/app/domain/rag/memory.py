"""Domain entities for per-user-per-KB conversation memory."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemoryConfig:
    """Per-KB memory configuration. Controls opt-in, summarization, and retrieval."""

    id: str
    tenant_id: str
    knowledge_base_id: str
    enabled: bool
    summarization_model_profile_id: str
    embedding_profile_id: str
    retention_days: int
    retrieval_top_k: int
    min_turns_to_summarize: int
    system_prompt: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MemoryChunk:
    """A summarized memory unit representing one completed conversation session."""

    id: str
    tenant_id: str
    knowledge_base_id: str
    user_id: str
    conversation_id: str | None
    summary: str
    qdrant_point_id: str
    embedding_profile_id: str
    turn_count: int
    expires_at: datetime
    created_at: datetime


DEFAULT_SYSTEM_PROMPT = """\
You are a memory summarizer. Given the following conversation messages from a knowledge base session, \
produce a concise summary capturing the user's key questions, findings, preferences, and any important \
context that would be useful in a future session.

Knowledge base: {{ knowledge_base_name }}
Turn count: {{ turn_count }}

Conversation:
{{ conversation_messages }}

Summary:"""
