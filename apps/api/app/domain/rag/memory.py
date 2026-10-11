"""Domain entities for per-user-per-KB conversation memory."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemoryConfig:
    """Project-owned memory configuration. Controls opt-in, summarization, and retrieval."""

    id: str
    tenant_id: str
    project_id: str | None
    knowledge_base_id: str | None
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
You are a memory eligibility and summarization assistant. Given the following conversation messages from \
a knowledge base session, identify only durable user-stated facts, preferences, or context that would be \
useful in a future session. Do not retain transient questions, assistant-only claims, retrieved document \
facts that the user did not adopt, secrets, or unsupported assumptions.

Knowledge base: {{ knowledge_base_name }}
Turn count: {{ turn_count }}

Conversation:
{{ conversation_messages }}

Return the memory decision as the required JSON object described by the runtime contract."""
