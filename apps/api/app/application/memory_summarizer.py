"""Background summarization service: conversation → summary → embed → Qdrant."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jinja2 import BaseLoader, Environment, TemplateSyntaxError

from app.core.settings import Settings
from app.domain.rag.memory import MemoryConfig

logger = logging.getLogger(__name__)

_QDRANT_MEMORY_COLLECTION = "memory"
_SUMMARIZE_TIMEOUT_S = 30
_QDRANT_TIMEOUT_S = 10


def render_system_prompt(template_str: str, *, conversation_messages: str, knowledge_base_name: str, turn_count: int) -> str:
    env = Environment(loader=BaseLoader(), autoescape=False)
    tmpl = env.from_string(template_str)
    return tmpl.render(
        conversation_messages=conversation_messages,
        knowledge_base_name=knowledge_base_name,
        turn_count=turn_count,
    )


def validate_jinja2_template(template_str: str) -> bool:
    """Return True if template is valid Jinja2, False otherwise."""
    try:
        env = Environment(loader=BaseLoader(), autoescape=False)
        env.parse(template_str)
        return True
    except TemplateSyntaxError:
        return False


class MemorySummarizer:
    """Orchestrates: load messages → render prompt → call LLM → embed → upsert Qdrant → save DB."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def summarize(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
        session: "AsyncSession",
    ) -> bool:
        """Summarize a conversation and persist a MemoryChunk. Returns True if chunk was created."""
        from app.infrastructure.rag_answer_trace import ConversationRecord
        from app.infrastructure.rag_catalog import (
            MemoryChunkRecord,
            MemoryConfigRecord,
            SqlAlchemyMemoryChunkRepository,
            SqlAlchemyMemoryConfigRepository,
        )
        from app.infrastructure.rag_conversations import SqlAlchemyConversationHistoryRepository
        from sqlalchemy import select, update

        # 1. Load memory config
        memory_config_repo = SqlAlchemyMemoryConfigRepository(session)
        config = await memory_config_repo.find_by_knowledge_base(
            tenant_id=tenant_id, knowledge_base_id=knowledge_base_id
        )
        if config is None or not config.enabled:
            logger.debug("[memory.summarize] memory not enabled for kb=%s", knowledge_base_id)
            return False

        # 2. Check already summarized
        chunk_repo = SqlAlchemyMemoryChunkRepository(session)
        already = await chunk_repo.is_conversation_summarized(conversation_id=conversation_id)
        if already:
            logger.debug("[memory.summarize] already summarized conversation=%s", conversation_id)
            return False

        # 3. Load conversation messages
        conv_repo = SqlAlchemyConversationHistoryRepository(session)
        messages = await conv_repo.recent_messages(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=200,
        )
        turn_count = len(messages)
        if turn_count < config.min_turns_to_summarize:
            logger.debug("[memory.summarize] too few turns (%d < %d)", turn_count, config.min_turns_to_summarize)
            return False

        # 4. Load KB name
        from app.infrastructure.rag_catalog import SqlAlchemyKnowledgeBaseRepository
        kb_repo = SqlAlchemyKnowledgeBaseRepository(session)
        kb = await kb_repo.find_by_id(tenant_id=tenant_id, knowledge_base_id=knowledge_base_id)
        kb_name = kb.name if kb else knowledge_base_id

        # 5. Render prompt
        conversation_text = "\n".join(
            f"{msg.speaker.value}: {msg.content}" for msg in messages
        )
        prompt = render_system_prompt(
            config.system_prompt,
            conversation_messages=conversation_text,
            knowledge_base_name=kb_name,
            turn_count=turn_count,
        )

        # 6. Call summarization LLM
        summary = await self._call_llm(
            tenant_id=tenant_id,
            model_profile_id=config.summarization_model_profile_id,
            prompt=prompt,
            session=session,
        )
        if not summary:
            logger.warning("[memory.summarize] LLM returned empty summary for conversation=%s", conversation_id)
            return False

        # 7. Embed summary
        vector = await self._embed(
            tenant_id=tenant_id,
            model_profile_id=config.embedding_profile_id,
            text=summary,
            session=session,
        )

        # 8. Upsert to Qdrant
        point_id = str(uuid4())
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=config.retention_days)
        await self._upsert_qdrant(
            point_id=point_id,
            vector=vector,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
            chunk_id=point_id,
            expires_at=expires_at,
        )

        # 9. Save MemoryChunk to DB
        await chunk_repo.create(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
            conversation_id=conversation_id,
            summary=summary,
            qdrant_point_id=point_id,
            embedding_profile_id=config.embedding_profile_id,
            turn_count=turn_count,
            expires_at=expires_at,
        )

        # 10. Mark conversation as summarized
        await session.execute(
            update(ConversationRecord)
            .where(ConversationRecord.id == conversation_id)
            .values(summarized=True)
        )
        await session.commit()

        logger.info("[memory.summarize] created chunk for conversation=%s kb=%s", conversation_id, knowledge_base_id)
        return True

    async def _call_llm(
        self,
        *,
        tenant_id: str,
        model_profile_id: str,
        prompt: str,
        session: "AsyncSession",
    ) -> str:
        from app.infrastructure.rag_catalog import SqlAlchemyModelProfileRepository
        profile_repo = SqlAlchemyModelProfileRepository(session)
        profile = await profile_repo.find_by_id(tenant_id=tenant_id, profile_id=model_profile_id)
        if profile is None:
            raise ValueError(f"Model profile {model_profile_id} not found")

        api_key = await _get_api_key(profile.provider, tenant_id, session, self._settings)

        if profile.provider == "openai":
            return await asyncio.wait_for(
                _call_openai_llm(profile.model, prompt, api_key),
                timeout=_SUMMARIZE_TIMEOUT_S,
            )
        elif profile.provider == "ollama":
            base_url = api_key or getattr(self._settings, "ollama_base_url", "http://localhost:11434") or "http://localhost:11434"
            return await asyncio.wait_for(
                _call_ollama_llm(profile.model, prompt, base_url),
                timeout=_SUMMARIZE_TIMEOUT_S,
            )
        else:
            raise ValueError(f"Unsupported LLM provider for summarization: {profile.provider}")

    async def _embed(
        self,
        *,
        tenant_id: str,
        model_profile_id: str,
        text: str,
        session: "AsyncSession",
    ) -> list[float]:
        from app.infrastructure.providers.registry import ProviderRegistry
        from app.infrastructure.rag_catalog import SqlAlchemyModelProfileRepository
        profile_repo = SqlAlchemyModelProfileRepository(session)
        profile = await profile_repo.find_by_id(tenant_id=tenant_id, profile_id=model_profile_id)
        if profile is None:
            raise ValueError(f"Embedding profile {model_profile_id} not found")

        registry = ProviderRegistry(self._settings)
        vectors = await registry.embed_with_fallback(
            texts=[text],
            primary_provider=profile.provider,
            primary_model=profile.model,
            tenant_id=tenant_id,
            session=session,
        )
        return vectors[0]

    async def _upsert_qdrant(
        self,
        *,
        point_id: str,
        vector: list[float],
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
        chunk_id: str,
        expires_at: datetime,
    ) -> None:
        import httpx
        base_url = self._settings.qdrant_url.rstrip("/")
        headers = {"api-key": self._settings.qdrant_api_key} if self._settings.qdrant_api_key else {}
        payload = {
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "user_id": user_id,
            "chunk_id": chunk_id,
            "expires_at": expires_at.isoformat(),
        }
        async with httpx.AsyncClient(timeout=_QDRANT_TIMEOUT_S) as client:
            resp = await client.put(
                f"{base_url}/collections/{_QDRANT_MEMORY_COLLECTION}/points",
                headers=headers,
                json={"points": [{"id": point_id, "vector": vector, "payload": payload}]},
            )
            resp.raise_for_status()

    async def delete_qdrant_points_by_ids(self, *, point_ids: list[str]) -> None:
        """Delete specific Qdrant points by their IDs."""
        if not point_ids:
            return
        import httpx
        base_url = self._settings.qdrant_url.rstrip("/")
        headers = {"api-key": self._settings.qdrant_api_key} if self._settings.qdrant_api_key else {}
        async with httpx.AsyncClient(timeout=_QDRANT_TIMEOUT_S) as client:
            resp = await client.post(
                f"{base_url}/collections/{_QDRANT_MEMORY_COLLECTION}/points/delete",
                headers=headers,
                json={"points": point_ids},
            )
            resp.raise_for_status()


async def _get_api_key(provider: str, tenant_id: str, session: "AsyncSession", settings: Settings) -> str | None:
    from app.infrastructure.providers.registry import get_provider_api_key
    key_name = "api_key" if provider == "openai" else "base_url" if provider == "ollama" else None
    if key_name is None:
        return None
    return await get_provider_api_key(provider, key_name, tenant_id, session, settings)


async def _call_openai_llm(model: str, prompt: str, api_key: str | None) -> str:
    if not api_key:
        raise ValueError("OpenAI API key not configured")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""


async def _call_ollama_llm(model: str, prompt: str, base_url: str) -> str:
    import httpx
    async with httpx.AsyncClient(timeout=_SUMMARIZE_TIMEOUT_S) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


# fix missing import for type hint
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
