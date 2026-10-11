"""
Dev trace utility — structured observability for ingestion and query pipelines.

Activated via RAG_DEV_TRACE env var:
  off     (default) — no-op, zero overhead
  summary — human-readable one-liner per event to stdout
  verbose — NDJSON per event to stdout (machine-parseable, pipe-friendly)

Usage:
    from app.core.dev_trace import get_tracer

    tracer = get_tracer()
    async with tracer.op("ingestion.embed", version_id=vid, vectors=128, verbose_meta={"dim": 1536}):
        ...  # actual work here
"""

from __future__ import annotations

import contextlib
import json
import sys
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal, TypeAlias

DevTraceMode: TypeAlias = Literal["off", "summary", "verbose"]


def _tail(text: str, n: int = 300) -> str:
    """Return the last `n` characters of `text`."""
    if not text:
        return ""
    return text[-n:]


class DevTracer:
    """Structured dev trace emitter. Thread-safe for CPython (GIL ensures atomic print)."""

    def __init__(self, mode: DevTraceMode) -> None:
        self._mode = mode
        self._enabled = mode != "off"

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def mode(self) -> str:
        return self._mode

    @contextlib.asynccontextmanager
    async def op(
        self,
        event: str,
        verbose_meta: dict[str, Any] | None = None,
        **meta: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async context manager that times the wrapped block and emits a trace event on exit.

        Args:
            event: dot-namespaced event name e.g. "ingestion.embed"
            verbose_meta: fields included only in verbose mode (e.g. full sub-query list)
            **meta: fields included in both summary and verbose output
        """
        if not self._enabled:
            yield meta
            return

        t0 = time.monotonic()
        try:
            yield meta
        except BaseException as error:
            # Keep the original exception semantics while ensuring failures are
            # visible in dev traces without serializing exception contents.
            meta.setdefault("error_type", type(error).__name__)
            raise
        finally:
            ms = round((time.monotonic() - t0) * 1000, 1)
            self._emit(event, ms, meta, verbose_meta or {})

    def emit(self, event: str, verbose_meta: dict[str, Any] | None = None, **meta: Any) -> None:
        """Emit a trace event without timing (for point-in-time observations)."""
        if not self._enabled:
            return
        self._emit(event, None, meta, verbose_meta or {})

    def _emit(self, event: str, ms: float | None, meta: dict[str, Any], verbose_meta: dict[str, Any]) -> None:
        if self._mode == "summary":
            line = self._format_summary(event, ms, meta)
        else:
            line = self._format_verbose(event, ms, meta, verbose_meta)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def _format_summary(self, event: str, ms: float | None, meta: dict[str, Any]) -> str:
        parts = [f"[DEV] {event}"]
        for k, v in meta.items():
            if isinstance(v, str) and k in {"system_prompt", "user_prompt", "system_tail", "user_tail"}:
                v = _tail(v)
            elif isinstance(v, str) and len(v) > 120:
                v = v[:120] + "…"
            elif isinstance(v, (list, tuple, set)) and all(isinstance(item, str) for item in v):
                v = ",".join(v)
            parts.append(f"{k}={v}")
        if ms is not None:
            parts.append(f"ms={ms}")
        return " ".join(parts)

    def _format_verbose(
        self,
        event: str,
        ms: float | None,
        meta: dict[str, Any],
        verbose_meta: dict[str, Any],
    ) -> str:
        combined_meta = {**meta, **verbose_meta}
        payload: dict[str, Any] = {
            "event": event,
            "ts": datetime.now(UTC).isoformat(),
        }
        for key, value in combined_meta.items():
            if key in {"system_prompt", "user_prompt"}:
                key = key.removesuffix("_prompt") + "_tail"
                value = _tail(str(value))
            elif key in {"system_tail", "user_tail"}:
                value = _tail(str(value))
            payload[key] = value
        if ms is not None:
            payload["ms"] = ms
        return json.dumps(payload, default=str)


class _NoopTracer(DevTracer):
    """Zero-overhead tracer used when RAG_DEV_TRACE=off."""

    def __init__(self) -> None:
        super().__init__("off")

    @contextlib.asynccontextmanager
    async def op(
        self,
        event: str,
        verbose_meta: dict[str, Any] | None = None,
        **meta: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        yield meta

    def emit(self, event: str, verbose_meta: dict[str, Any] | None = None, **meta: Any) -> None:
        return


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_tracer: DevTracer | None = None


def get_tracer() -> DevTracer:
    """Return the module-level singleton DevTracer, lazily initialised from settings."""
    global _tracer
    if _tracer is None:
        from app.core.settings import get_settings

        mode = get_settings().rag_dev_trace
        _tracer = _NoopTracer() if mode == "off" else DevTracer(mode)
    return _tracer


def reset_tracer() -> None:
    """Reset singleton — used in tests only."""
    global _tracer
    _tracer = None
