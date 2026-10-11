"""LLM-based query decomposer.

Decomposes a complex query into atomic sub-queries using an LLM.
Uses Jinja2 templates for prompt customization.
Falls back to original query if LLM call fails or returns invalid output.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from jinja2 import BaseLoader, Environment
from jinja2.sandbox import SandboxedEnvironment

from app.core.dev_trace import _tail, get_tracer
from app.core.llm_rollout_trace import get_rollout_trace

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.settings import Settings
    from app.domain.rag.catalog import DecompositionConfig
    from app.domain.rag.profiles import ModelProfile

logger = logging.getLogger(__name__)

_JINJA_ENV: Environment = SandboxedEnvironment(loader=BaseLoader())

DEFAULT_SYSTEM_PROMPT = (
    "You are a query decomposition assistant. "
    "Given a complex user query, break it into {{ max_sub_queries }} or fewer "
    "atomic sub-queries that can each be answered independently from a document "
    "retrieval system. Return ONLY a JSON array of strings. No explanation, no "
    'markdown, no code block. Example: ["sub-query 1", "sub-query 2"]'
)

DEFAULT_USER_PROMPT_TEMPLATE = "Query: {{ query }}\nKnowledge base: {{ knowledge_base_name }}\nSub-queries (max {{ max_sub_queries }}):"

LLM_TIMEOUT_SECONDS = 10


@dataclass
class DecompositionResult:
    sub_queries: list[str]
    fallback: bool
    fallback_reason: str | None = None


def validate_template(template_str: str) -> None:
    """Validate a Jinja2 template string. Raises TemplateSyntaxError if invalid."""
    _JINJA_ENV.parse(template_str)


def _render(template_str: str, context: dict[str, object]) -> str:
    tmpl = _JINJA_ENV.from_string(template_str)
    return tmpl.render(**context)


async def _call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str,
    api_key: str,
    timeout: float = LLM_TIMEOUT_SECONDS,
    operation: str = "query.decompose",
) -> str:
    from openai import AsyncOpenAI

    request_body: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": 512,
    }
    trace = get_rollout_trace()
    request_seq = trace.record(
        "llm_request",
        {"provider": "openai", "operation": operation, "model": model, "request": request_body, "attempt": 1},
    )
    client = cast(Any, AsyncOpenAI(api_key=api_key))
    try:
        response = await asyncio.wait_for(client.chat.completions.create(**request_body), timeout=timeout)
        content = cast(str, response.choices[0].message.content or "")
        trace.record(
            "llm_response",
            {"provider": "openai", "operation": operation, "request_seq": request_seq, "response": response, "content": content},
            parent_seq=request_seq,
        )
        return content
    except asyncio.CancelledError:
        trace.record(
            "llm_error",
            {"provider": "openai", "operation": operation, "request_seq": request_seq, "error": "cancelled"},
            parent_seq=request_seq,
        )
        raise
    except Exception as error:
        trace.record(
            "llm_error",
            {"provider": "openai", "operation": operation, "request_seq": request_seq, "error_type": type(error).__name__, "error": str(error)},
            parent_seq=request_seq,
        )
        raise


async def _call_ollama(
    system_prompt: str,
    user_prompt: str,
    model: str,
    base_url: str,
    timeout: float = LLM_TIMEOUT_SECONDS,
    operation: str = "query.decompose",
) -> str:
    import httpx

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    trace = get_rollout_trace()
    request_seq = trace.record(
        "llm_request",
        {
            "provider": "ollama",
            "operation": operation,
            "model": model,
            "endpoint": f"{base_url.rstrip('/')}/api/chat",
            "request": payload,
            "attempt": 1,
        },
    )
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        try:
            response = await client.post("/api/chat", json=payload)
            data = response.json()
            status_code = getattr(response, "status_code", None)
            response.raise_for_status()
            content = cast(str, data.get("message", {}).get("content", ""))
            trace.record(
                "llm_response",
                {"provider": "ollama", "operation": operation, "request_seq": request_seq, "status_code": status_code, "response": data, "content": content},
                parent_seq=request_seq,
            )
            return content
        except asyncio.CancelledError:
            trace.record(
                "llm_error",
                {"provider": "ollama", "operation": operation, "request_seq": request_seq, "error": "cancelled"},
                parent_seq=request_seq,
            )
            raise
        except Exception as error:
            trace.record(
                "llm_error",
                {
                    "provider": "ollama",
                    "operation": operation,
                    "request_seq": request_seq,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "status_code": getattr(response, "status_code", None) if "response" in locals() else None,
                },
                parent_seq=request_seq,
            )
            raise


def _parse_sub_queries(raw: str, max_sub_queries: int) -> list[str]:
    """Parse LLM output into a list of sub-query strings."""
    raw = raw.strip()
    # Strip markdown code block if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array")
    result = [str(q).strip() for q in parsed if str(q).strip()]
    return result[:max_sub_queries]


class QueryDecomposer:
    """Decomposes a complex query into sub-queries via LLM."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def decompose(
        self,
        *,
        query: str,
        config: DecompositionConfig,
        knowledge_base_name: str,
        model_profile: ModelProfile,
        session: AsyncSession | None = None,
    ) -> DecompositionResult:
        """Decompose query into sub-queries. Returns fallback on any failure."""
        context = {
            "query": query,
            "knowledge_base_name": knowledge_base_name,
            "max_sub_queries": config.max_sub_queries,
        }

        try:
            system_prompt = _render(config.system_prompt, context)
            user_prompt = _render(config.user_prompt_template, context)
        except Exception as e:
            logger.warning("Template render failed for decomposition: %s", e)
            return DecompositionResult(
                sub_queries=[query],
                fallback=True,
                fallback_reason=f"template_render_error: {e}",
            )

        raw: str | None = None
        trace = get_rollout_trace()
        try:
            tracer = get_tracer()
            verbose_meta: dict[str, Any] = {}
            async with tracer.op(
                "query.decompose",
                count=0,
                fallback=False,
                system_tail=_tail(system_prompt) if tracer.enabled else "",
                user_tail=_tail(user_prompt) if tracer.enabled else "",
                verbose_meta=verbose_meta,
            ) as trace_meta:
                raw = await self._call_llm(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model_profile=model_profile,
                    tenant_id=config.tenant_id,
                    session=session,
                )
                sub_queries = _parse_sub_queries(raw, config.max_sub_queries)
                if not sub_queries:
                    trace_meta.update(count=0, fallback=True)
                    return DecompositionResult(
                        sub_queries=[query],
                        fallback=True,
                        fallback_reason="empty_sub_queries",
                    )
                trace_meta.update(count=len(sub_queries), fallback=False)
                verbose_meta["sub_queries"] = sub_queries
                return DecompositionResult(sub_queries=sub_queries, fallback=False)
        except TimeoutError:
            logger.warning("LLM decomposition timed out for query: %.80s", query)
            trace.record("llm_error", {"operation": "query.decompose", "error": "timeout"})
            trace.record("llm_fallback", {"operation": "query.decompose", "reason": "timeout", "query": query})
            return DecompositionResult(
                sub_queries=[query],
                fallback=True,
                fallback_reason="timeout",
            )
        except Exception as e:
            logger.warning("LLM decomposition failed: %s", e)
            if raw is not None:
                trace.record(
                    "llm_parse_error",
                    {"operation": "query.decompose", "raw_response": raw, "error_type": type(e).__name__, "error": str(e)},
                )
            trace.record("llm_fallback", {"operation": "query.decompose", "reason": f"llm_error: {type(e).__name__}", "query": query})
            return DecompositionResult(
                sub_queries=[query],
                fallback=True,
                fallback_reason=f"llm_error: {type(e).__name__}",
            )

    async def _call_llm(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_profile: ModelProfile,
        tenant_id: str,
        session: AsyncSession | None,
    ) -> str:
        from app.infrastructure.providers.registry import get_provider_api_key

        provider = model_profile.provider
        model = model_profile.model

        if provider == "openai":
            api_key = await get_provider_api_key(
                provider="openai",
                key_name="api_key",
                tenant_id=tenant_id,
                session=session,
                settings=self._settings,
            )
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            return await _call_openai(system_prompt, user_prompt, model, api_key, operation="query.decompose")

        elif provider == "ollama":
            base_url = (
                await get_provider_api_key(
                    provider="ollama",
                    key_name="base_url",
                    tenant_id=tenant_id,
                    session=session,
                    settings=self._settings,
                )
                or getattr(self._settings, "ollama_base_url", "http://localhost:11434")
                or "http://localhost:11434"
            )
            return await _call_ollama(system_prompt, user_prompt, model, base_url, operation="query.decompose")

        else:
            raise ValueError(f"Unsupported LLM provider for decomposition: {provider}")
