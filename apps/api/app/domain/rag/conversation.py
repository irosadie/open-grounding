"""Bounded, tenant-owned conversation history for query normalization."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ConversationSpeaker(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


@dataclass(frozen=True)
class ConversationMessage:
    id: str
    tenant_id: str
    conversation_id: str
    speaker: ConversationSpeaker
    content: str
    created_at: datetime
