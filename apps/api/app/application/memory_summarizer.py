"""Background summarization service: conversation → summary → embed → Qdrant."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from jinja2 import BaseLoader, Environment, TemplateSyntaxError

from app.core.llm_rollout_trace import get_rollout_trace
from app.core.settings import Settings

logger = logging.getLogger(__name__)

_QDRANT_MEMORY_COLLECTION = "memory"
_SUMMARIZE_TIMEOUT_S = 30
_QDRANT_TIMEOUT_S = 10
MAX_MEMORY_SUMMARY_CHARS = 4_000
MAX_MEMORY_REASON_CHARS = 500

_MEMORY_DECISION_CONTRACT = """\

Memory eligibility policy:
- Store only durable user-stated facts, preferences, goals, or context that can help in a future session.
- Treat USER messages as the authority for personal facts. Assistant messages may contain retrieved source
  content and are not proof that a fact belongs to the user.
- An explicit USER request to remember, save, or store a durable personal fact is a strong signal to store
  that fact, but it does not override the exclusions for secrets, unsupported assumptions, source-only facts,
  or transient questions.
- When an explicit save request contains a concrete fact or preference, summarize that fact or preference
  itself. Do not store a generic consent, policy statement, or summary of the request instead. For example,
  "my name is Alya" must be summarized as the user's name being Alya.
- Do not store transient questions, one-off answers, source-only facts, secrets, or unsupported assumptions.
- If there is no durable user memory, set should_store to false and summary to null.

Return ONLY valid JSON with exactly this shape:
{"should_store": true|false, "summary": "bounded memory summary or null", "reason": "short diagnostic reason"}
"""

_EXPLICIT_MEMORY_REQUEST_RE = re.compile(
    r"\b(?:simpan|menyimpan|ingat|ingatlah|catat|catatlah|save|remember|store|keep)\b"
    r"(?:(?![.!?]).){0,120}"
    r"\b(?:saya|aku|i|me|my|nama|name|preferensi|preference|informasi|information|info|data|ini|this|that)\b",
    re.IGNORECASE,
)

_EXPLICIT_MEMORY_SECRET_RE = re.compile(
    r"\b(?:password|passcode|kata sandi|token|api key|apikey|secret|rahasia|otp|pin|private key|credential)\b",
    re.IGNORECASE,
)
_EXPLICIT_MEMORY_NAME_PATTERNS = (
    re.compile(r"\bsaya adalah\s+([^.!?\n]{1,80})", re.IGNORECASE),
    re.compile(r"\b(?:nama saya|saya bernama|my name is)\s*(?:adalah|is)?\s*[:\-]?\s*([^,.!?\n]{1,80})", re.IGNORECASE),
)
_EXPLICIT_MEMORY_PREFERENCE_PATTERN = re.compile(
    r"\b(?:saya suka|saya menyukai|saya lebih suka|i like|i prefer)\s+([^.!?\n]{1,160})",
    re.IGNORECASE,
)
_EXPLICIT_MEMORY_SAFETY_REJECTION_MARKERS = (
    "secret",
    "rahasia",
    "password",
    "kata sandi",
    "token",
    "api key",
    "source",
    "sumber",
    "document",
    "dokumen",
    "unsupported",
    "tidak didukung",
    "transient",
    "sementara",
)

_EXPLICIT_MEMORY_DECISION_CONTRACT = """

HARD RULE FOR THIS CONVERSATION:
An explicit USER request to save personal information was detected. If that request
contains a concrete, non-secret fact or preference, set should_store to true and
summarize the fact or preference itself. Do not return false merely because the user is
also granting permission to save it, and do not summarize permission or consent instead
of the concrete fact. Reject the content only when it is secret, unsupported, source-only,
or otherwise excluded by the memory policy.

ATURAN WAJIB UNTUK PERMINTAAN BAHASA INDONESIA:
Jika USER meminta untuk menyimpan/mengingat informasi dan dalam pesan yang sama
menyebut fakta konkret tentang dirinya, set should_store menjadi true dan rangkum
faktanya. Contoh: "simpan informasi nama saya, saya adalah Alya" harus dirangkum
sebagai fakta bahwa nama pengguna adalah Alya, bukan sebagai izin umum atau persetujuan
menyimpan percakapan. Aturan ini tetap tidak berlaku untuk rahasia, fakta yang tidak
didukung, fakta dari sumber saja, atau pertanyaan sementara.
"""


@dataclass(frozen=True)
class MemoryDecision:
    should_store: bool
    summary: str | None
    reason: str | None = None


def parse_memory_decision(raw: str, *, max_summary_chars: int = MAX_MEMORY_SUMMARY_CHARS) -> MemoryDecision:
    """Parse a memory LLM response and fail closed for invalid output."""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return MemoryDecision(False, None, "invalid_json")

    if not isinstance(payload, dict) or type(payload.get("should_store")) is not bool:
        return MemoryDecision(False, None, "invalid_should_store")

    should_store = bool(payload["should_store"])
    summary = payload.get("summary")
    reason = payload.get("reason")
    normalized_reason = reason.strip()[:MAX_MEMORY_REASON_CHARS] if isinstance(reason, str) else None

    if not should_store:
        return MemoryDecision(False, None, normalized_reason or "not_memory_worthy")
    if not isinstance(summary, str) or not summary.strip():
        return MemoryDecision(False, None, "missing_summary")

    normalized_summary = summary.strip()
    if len(normalized_summary) > max_summary_chars:
        return MemoryDecision(False, None, "summary_too_long")

    return MemoryDecision(True, normalized_summary, normalized_reason or "accepted")


def has_explicit_memory_request(messages: Sequence[object]) -> bool:
    """Return whether a USER message explicitly asks to retain personal context."""
    for message in messages:
        speaker = getattr(message, "speaker", None)
        speaker_value = getattr(speaker, "value", speaker)
        if str(speaker_value).upper() != "USER":
            continue
        content = getattr(message, "content", None)
        if isinstance(content, str) and _EXPLICIT_MEMORY_REQUEST_RE.search(" ".join(content.casefold().split())):
            return True
    return False


def extract_explicit_memory_summary(messages: Sequence[object]) -> str | None:
    """Extract only high-confidence, non-secret facts from an explicit save request."""
    for message in messages:
        speaker = getattr(message, "speaker", None)
        speaker_value = getattr(speaker, "value", speaker)
        if str(speaker_value).upper() != "USER":
            continue
        content = getattr(message, "content", None)
        if not isinstance(content, str) or _EXPLICIT_MEMORY_SECRET_RE.search(content):
            continue
        for pattern in _EXPLICIT_MEMORY_NAME_PATTERNS:
            match = pattern.search(content)
            if match:
                value = " ".join(match.group(1).split()).strip(" :-")
                if value:
                    return f"Pengguna menyatakan bahwa namanya adalah {value}."
        preference_match = _EXPLICIT_MEMORY_PREFERENCE_PATTERN.search(content)
        if preference_match:
            value = " ".join(preference_match.group(1).split()).strip(" :-")
            if value:
                return f"Pengguna menyatakan preferensi: {value}."
    return None


def _is_explicit_memory_safety_rejection(reason: str | None) -> bool:
    normalized = (reason or "").casefold()
    return any(marker in normalized for marker in _EXPLICIT_MEMORY_SAFETY_REJECTION_MARKERS)


def render_system_prompt(
    template_str: str,
    *,
    conversation_messages: str,
    knowledge_base_name: str,
    turn_count: int,
    explicit_memory_request: bool = False,
) -> str:
    env = Environment(loader=BaseLoader(), autoescape=False)
    tmpl = env.from_string(template_str)
    rendered = tmpl.render(
        conversation_messages=conversation_messages,
        knowledge_base_name=knowledge_base_name,
        turn_count=turn_count,
    )
    explicit_contract = _EXPLICIT_MEMORY_DECISION_CONTRACT if explicit_memory_request else ""
    return f"{rendered}\n{_MEMORY_DECISION_CONTRACT}{explicit_contract}"


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
        project_id: str | None = None,
        user_id: str,
        session: AsyncSession,
    ) -> bool:
        """Summarize a conversation and persist a MemoryChunk. Returns True if chunk was created."""
        from sqlalchemy import update

        from app.infrastructure.rag_answer_trace import ConversationRecord
        from app.infrastructure.rag_catalog import (
            SqlAlchemyMemoryChunkRepository,
            SqlAlchemyMemoryConfigRepository,
        )
        from app.infrastructure.rag_conversations import SqlAlchemyConversationHistoryRepository

        # 1. Load memory config
        memory_config_repo = SqlAlchemyMemoryConfigRepository(session)
        config = None
        if project_id is not None:
            config = await memory_config_repo.find_by_project(tenant_id=tenant_id, project_id=project_id)
        if config is None:
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
        explicit_memory_request = has_explicit_memory_request(messages)
        if turn_count < config.min_turns_to_summarize and not explicit_memory_request:
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
            explicit_memory_request=explicit_memory_request,
        )

        # 6. Call summarization LLM
        decision = await self._call_llm(
            tenant_id=tenant_id,
            model_profile_id=config.summarization_model_profile_id,
            prompt=prompt,
            session=session,
        )
        explicit_summary = extract_explicit_memory_summary(messages) if explicit_memory_request else None
        if explicit_summary and (decision.should_store or not _is_explicit_memory_safety_rejection(decision.reason)):
            decision = MemoryDecision(True, explicit_summary, decision.reason or "explicit_user_fact")
        if not decision.should_store or not decision.summary:
            logger.info(
                "[memory.summarize] memory not stored for conversation=%s reason=%s",
                conversation_id,
                decision.reason or "not_memory_worthy",
            )
            return False
        summary = decision.summary

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
        session: AsyncSession,
    ) -> MemoryDecision:
        from app.infrastructure.rag_catalog import SqlAlchemyModelProfileRepository
        profile_repo = SqlAlchemyModelProfileRepository(session)
        profile = await profile_repo.find_by_id(tenant_id=tenant_id, profile_id=model_profile_id)
        if profile is None:
            raise ValueError(f"Model profile {model_profile_id} not found")

        api_key = await _get_api_key(profile.provider, tenant_id, session, self._settings)

        if profile.provider == "openai":
            raw = await asyncio.wait_for(
                _call_openai_llm(profile.model, prompt, api_key),
                timeout=_SUMMARIZE_TIMEOUT_S,
            )
        elif profile.provider == "ollama":
            base_url = api_key or getattr(self._settings, "ollama_base_url", "http://localhost:11434") or "http://localhost:11434"
            raw = await asyncio.wait_for(
                _call_ollama_llm(profile.model, prompt, base_url),
                timeout=_SUMMARIZE_TIMEOUT_S,
            )
        else:
            raise ValueError(f"Unsupported LLM provider for summarization: {profile.provider}")
        return parse_memory_decision(raw)

    async def _embed(
        self,
        *,
        tenant_id: str,
        model_profile_id: str,
        text: str,
        session: AsyncSession,
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
            await _ensure_memory_collection(
                client=client,
                base_url=base_url,
                headers=headers,
                vector_size=len(vector),
            )
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


async def _ensure_memory_collection(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    vector_size: int,
) -> None:
    """Create the memory collection lazily for fresh Qdrant instances."""
    response = await client.get(
        f"{base_url}/collections/{_QDRANT_MEMORY_COLLECTION}",
        headers=headers,
    )
    if response.status_code == 200:
        return
    if response.status_code != 404:
        response.raise_for_status()

    created = await client.put(
        f"{base_url}/collections/{_QDRANT_MEMORY_COLLECTION}",
        headers=headers,
        json={"vectors": {"size": vector_size, "distance": "Cosine"}},
    )
    if created.status_code not in (200, 201, 202, 409):
        created.raise_for_status()


async def _get_api_key(provider: str, tenant_id: str, session: AsyncSession, settings: Settings) -> str | None:
    from app.infrastructure.providers.registry import get_provider_api_key
    key_name = "api_key" if provider == "openai" else "base_url" if provider == "ollama" else None
    if key_name is None:
        return None
    return await get_provider_api_key(provider, key_name, tenant_id, session, settings)


async def _call_openai_llm(model: str, prompt: str, api_key: str | None) -> str:
    if not api_key:
        raise ValueError("OpenAI API key not configured")
    from openai import AsyncOpenAI

    request_body: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 512,
    }
    trace = get_rollout_trace()
    request_seq = trace.record(
        "llm_request",
        {"provider": "openai", "operation": "memory.summarize", "model": model, "request": request_body, "attempt": 1},
    )
    client = cast(Any, AsyncOpenAI(api_key=api_key))
    try:
        resp = await client.chat.completions.create(**request_body)
        content = resp.choices[0].message.content or ""
        trace.record(
            "llm_response",
            {"provider": "openai", "operation": "memory.summarize", "request_seq": request_seq, "response": resp, "content": content},
            parent_seq=request_seq,
        )
        return content
    except asyncio.CancelledError:
        trace.record(
            "llm_error",
            {"provider": "openai", "operation": "memory.summarize", "request_seq": request_seq, "error": "cancelled"},
            parent_seq=request_seq,
        )
        raise
    except Exception as error:
        trace.record(
            "llm_error",
            {"provider": "openai", "operation": "memory.summarize", "request_seq": request_seq, "error_type": type(error).__name__, "error": str(error)},
            parent_seq=request_seq,
        )
        raise


async def _call_ollama_llm(model: str, prompt: str, base_url: str) -> str:
    import httpx

    request_body: dict[str, object] = {"model": model, "prompt": prompt, "stream": False}
    trace = get_rollout_trace()
    request_seq = trace.record(
        "llm_request",
        {
            "provider": "ollama",
            "operation": "memory.summarize",
            "model": model,
            "endpoint": f"{base_url.rstrip('/')}/api/generate",
            "request": request_body,
            "attempt": 1,
        },
    )
    async with httpx.AsyncClient(timeout=_SUMMARIZE_TIMEOUT_S) as client:
        try:
            resp = await client.post(f"{base_url.rstrip('/')}/api/generate", json=request_body)
            response_body = resp.json()
            status_code = getattr(resp, "status_code", None)
            resp.raise_for_status()
            response = response_body.get("response")
            content = response if isinstance(response, str) else ""
            trace.record(
                "llm_response",
                {"provider": "ollama", "operation": "memory.summarize", "request_seq": request_seq, "status_code": status_code, "response": response_body, "content": content},
                parent_seq=request_seq,
            )
            return content
        except asyncio.CancelledError:
            trace.record(
                "llm_error",
                {"provider": "ollama", "operation": "memory.summarize", "request_seq": request_seq, "error": "cancelled"},
                parent_seq=request_seq,
            )
            raise
        except Exception as error:
            trace.record(
                "llm_error",
                {
                    "provider": "ollama",
                    "operation": "memory.summarize",
                    "request_seq": request_seq,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "status_code": getattr(resp, "status_code", None) if "resp" in locals() else None,
                },
                parent_seq=request_seq,
            )
            raise


if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession
