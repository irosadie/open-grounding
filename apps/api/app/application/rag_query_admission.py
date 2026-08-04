"""Bounded in-process admission controls for the first query release."""

from collections import defaultdict
from time import monotonic

from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.tenant_context import TenantContext


class RagQueryAdmission:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._active: dict[str, int] = defaultdict(int)

    def admit(self, *, tenant: TenantContext, payload_bytes: int) -> None:
        if payload_bytes > self._settings.rag_query_max_payload_bytes:
            raise DomainError.query_payload_too_large()
        now = monotonic()
        window_start = now - 60
        timestamps = [timestamp for timestamp in self._requests[tenant.user_id] if timestamp >= window_start]
        if len(timestamps) >= self._settings.rag_query_requests_per_minute:
            raise DomainError.query_rate_limited()
        if self._active[tenant.user_id] >= self._settings.rag_query_max_concurrency:
            raise DomainError.query_concurrency_limited()
        timestamps.append(now)
        self._requests[tenant.user_id] = timestamps
        self._active[tenant.user_id] += 1

    def release(self, *, tenant: TenantContext) -> None:
        self._active[tenant.user_id] = max(0, self._active[tenant.user_id] - 1)
