from typing import Protocol

from app.domain.rag.conversation import ConversationMessage


class ConversationHistoryRepository(Protocol):
    async def recent_messages(
        self, *, tenant_id: str, user_id: str, conversation_id: str, limit: int
    ) -> list[ConversationMessage]: ...
