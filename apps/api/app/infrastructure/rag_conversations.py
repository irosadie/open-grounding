"""Tenant/user-scoped conversation history persistence."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.rag.conversation import ConversationMessage, ConversationSpeaker
from app.infrastructure.database import Base, utc_now


class ConversationMessageRecord(Base):
    __tablename__ = "rag_conversation_messages"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_conversations.id", ondelete="CASCADE"), nullable=False)
    speaker: Mapped[ConversationSpeaker] = mapped_column(Enum(ConversationSpeaker, name="ConversationSpeaker"), nullable=False)
    content: Mapped[str] = mapped_column(String(8_000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class SqlAlchemyConversationHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def recent_messages(self, *, tenant_id: str, user_id: str, conversation_id: str, limit: int) -> list[ConversationMessage]:
        from app.infrastructure.rag_answer_trace import ConversationRecord

        result = await self._session.execute(
            select(ConversationMessageRecord)
            .join(ConversationRecord, ConversationMessageRecord.conversation_id == ConversationRecord.id)
            .where(
                ConversationMessageRecord.tenant_id == tenant_id,
                ConversationRecord.tenant_id == tenant_id,
                ConversationRecord.user_id == user_id,
                ConversationMessageRecord.conversation_id == conversation_id,
            )
            .order_by(ConversationMessageRecord.created_at.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        return [ConversationMessage(row.id, row.tenant_id, row.conversation_id, row.speaker, row.content, row.created_at) for row in reversed(rows)]

    async def save_message(self, *, message: ConversationMessage) -> None:
        self._session.add(
            ConversationMessageRecord(
                id=message.id,
                tenant_id=message.tenant_id,
                conversation_id=message.conversation_id,
                speaker=message.speaker,
                content=message.content,
                created_at=message.created_at,
            )
        )
        await self._session.commit()

    async def ensure_conversation(self, *, tenant_id: str, user_id: str, conversation_id: str) -> None:
        from app.infrastructure.rag_answer_trace import ConversationRecord

        stmt = (
            insert(ConversationRecord)
            .values(id=conversation_id, tenant_id=tenant_id, user_id=user_id, summarized=False)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._session.execute(stmt)
        await self._session.commit()
