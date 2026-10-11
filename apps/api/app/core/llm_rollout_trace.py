"""Persistent, opt-in rollout tracing for LLM and tool execution.

The existing ``DevTracer`` is intentionally a lightweight stdout diagnostic.
This module records a complete per-trace JSONL timeline when
``RAG_LLM_TRACE_ENABLED=true``. It is deliberately best-effort: trace storage
must never change the application result or make a request fail.
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
from collections.abc import AsyncIterator, Mapping, Sequence
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeAlias
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

logger = logging.getLogger(__name__)

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "client_secret",
        "cookie",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    }
)
_URL_KEYS = frozenset({"base_url", "endpoint", "url", "uri"})
_SENSITIVE_QUERY_KEYS = frozenset({"access_token", "api_key", "apikey", "key", "secret", "token"})
ROLLOUT_EVENTS = frozenset(
    {
        "session_meta",
        "turn_started",
        "user_message",
        "context_assembled",
        "llm_request",
        "llm_stream_chunk",
        "llm_response",
        "llm_error",
        "llm_parse_error",
        "llm_fallback",
        "llm_retry",
        "tool_catalog",
        "tool_call_requested",
        "tool_execution_started",
        "tool_result",
        "tool_error",
        "policy_decision",
        "compaction",
        "agent_task_started",
        "agent_task_completed",
        "assistant_response",
        "safe_abstention",
        "turn_completed",
        "turn_failed",
        "trace_failed",
        "trace_completed",
    }
)


def new_trace_id() -> str:
    """Return a trace identifier suitable for filenames and event correlation."""
    return str(uuid4())


def _json_value(value: object) -> JsonValue:
    """Convert common SDK/Pydantic values into JSON-safe data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_value(model_dump())
        except Exception:
            pass
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_value(to_dict())
        except Exception:
            pass
    return str(value)


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc or not parsed.query:
        return value
    query = [
        (key, _REDACTED if key.lower() in _SENSITIVE_QUERY_KEYS else item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def redact(value: object, *, key: str | None = None) -> JsonValue:
    """Recursively redact credentials while retaining debug payload content."""
    normalized_key = key.lower() if key else ""
    if normalized_key in _SENSITIVE_KEYS or any(token in normalized_key for token in ("credential", "auth_header")):
        return _REDACTED
    if isinstance(value, str) and normalized_key in _URL_KEYS:
        return _redact_url(value)
    normalized = _json_value(value)
    if isinstance(normalized, dict):
        return {name: redact(item, key=name) for name, item in normalized.items()}
    if isinstance(normalized, list):
        return [redact(item) for item in normalized]
    return normalized


class RolloutTrace:
    """Append-only JSONL writer for one logical request or worker operation."""

    schema_version = 1

    def __init__(self, *, trace_id: str, trace_dir: Path, enabled: bool) -> None:
        self.trace_id = trace_id
        self._trace_dir = trace_dir
        self._enabled = enabled
        self._sequence = 0
        self._lock = threading.Lock()
        self._path: Path | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> Path | None:
        return self._path

    def record(
        self,
        event: str,
        payload: Mapping[str, object] | None = None,
        *,
        turn_id: str | None = None,
        parent_seq: int | None = None,
    ) -> int | None:
        """Append one event and return its sequence number when enabled."""
        if not self._enabled:
            return None

        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            envelope: dict[str, object] = {
                "schema_version": self.schema_version,
                "seq": sequence,
                "ts": datetime.now(UTC).isoformat(),
                "trace_id": self.trace_id,
                "event": event,
                "payload": redact(dict(payload or {})),
            }
            if turn_id is not None:
                envelope["turn_id"] = turn_id
            if parent_seq is not None:
                envelope["parent_seq"] = parent_seq
            try:
                line = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
                path = self._ensure_path()
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
                    handle.write("\n")
            except Exception:
                logger.exception("LLM rollout trace write failed for trace %s", self.trace_id)
            return sequence

    def _ensure_path(self) -> Path:
        if self._path is None:
            date_dir = self._trace_dir / datetime.now(UTC).strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True, exist_ok=True)
            self._path = date_dir / f"rollout-{self.trace_id}.jsonl"
        return self._path


class NoopRolloutTrace(RolloutTrace):
    """Disabled trace implementation that performs no serialization or I/O."""

    def __init__(self) -> None:
        super().__init__(trace_id="disabled", trace_dir=Path("."), enabled=False)

    def record(
        self,
        event: str,
        payload: Mapping[str, object] | None = None,
        *,
        turn_id: str | None = None,
        parent_seq: int | None = None,
    ) -> None:
        return None


_current_trace: ContextVar[RolloutTrace | None] = ContextVar("current_llm_rollout_trace", default=None)
_NOOP_TRACE = NoopRolloutTrace()


def get_rollout_trace() -> RolloutTrace:
    """Return the active trace or a disabled no-op trace."""
    return _current_trace.get() or _NOOP_TRACE


@contextlib.asynccontextmanager
async def rollout_context(
    *,
    trace_id: str | None = None,
    source: str,
    trace_dir: str | Path = ".runtime/llm-traces",
    enabled: bool = False,
    metadata: Mapping[str, object] | None = None,
) -> AsyncIterator[RolloutTrace]:
    """Create an async-local trace and record its lifecycle."""
    recorder = RolloutTrace(
        trace_id=trace_id or new_trace_id(),
        trace_dir=Path(trace_dir).expanduser(),
        enabled=enabled,
    )
    token = _current_trace.set(recorder)
    if enabled:
        recorder.record("session_meta", {"source": source, **dict(metadata or {})})
    try:
        yield recorder
    except BaseException as error:
        if enabled:
            recorder.record("trace_failed", {"error_type": type(error).__name__})
        raise
    finally:
        if enabled:
            recorder.record("trace_completed", {"source": source})
        _current_trace.reset(token)


def reset_rollout_trace() -> None:
    """Reset the context variable for isolated tests."""
    _current_trace.set(None)
