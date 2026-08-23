"""RAG infrastructure health and readiness diagnostics.

Distinguishes liveness from readiness. Liveness (``/health``) remains a
lightweight process-supervision contract. Readiness reports PostgreSQL, Redis,
Qdrant, object storage, deployment tenant, and active index-profile
availability without exposing credentials, internal URLs, or raw provider
error payloads.

Health probes are read-only and never perform a retrieval or mutation against
tenant-owned data. A dependency that cannot be reached is reported as
``unavailable``; liveness remains ``ok`` so process supervision does not
restart the API for an external dependency outage.
"""

from dataclasses import dataclass, field

from app.core.settings import RAG_RUNTIME_PRODUCTION, Settings


@dataclass(frozen=True)
class ComponentHealth:
    """Redacted health status for a single dependency."""

    name: str
    available: bool
    detail: str | None = None


@dataclass(frozen=True)
class ReadinessReport:
    """Aggregated readiness report safe to return over HTTP."""

    status: str
    components: list[ComponentHealth] = field(default_factory=list)
    deployment_tenant_id: str | None = None
    rag_enabled: bool = False
    rag_runtime_mode: str = "development"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "ragEnabled": self.rag_enabled,
            "ragRuntimeMode": self.rag_runtime_mode,
            "deploymentTenantId": self.deployment_tenant_id,
            "components": [{"name": c.name, "available": c.available, "detail": c.detail} for c in self.components],
        }


def _redact_error(error: BaseException) -> str:
    """Return a generic, credential-free detail string for an error."""
    name = type(error).__name__
    return f"{name}: unavailable"


async def _check_postgres(settings: Settings) -> ComponentHealth:
    from sqlalchemy import text as sa_text

    from app.infrastructure.database import create_session_factory

    try:
        session_factory = create_session_factory(settings)
        async with session_factory() as session:
            await session.execute(sa_text("SELECT 1"))
        return ComponentHealth(name="postgresql", available=True)
    except Exception as error:  # noqa: BLE001
        return ComponentHealth(name="postgresql", available=False, detail=_redact_error(error))


async def _check_redis(_settings: Settings) -> ComponentHealth:
    """Probe shared Redis availability for the Node worker that depends on it.

    The Python API does not own a Redis client; this check is informational.
    If the optional redis package is not installed, the component is reported
    unavailable without raising.
    """
    try:
        import redis.asyncio as redis  # type: ignore[import-not-found]

        client = redis.from_url("redis://127.0.0.1:6379/0")
        await client.ping()
        await client.aclose()
        return ComponentHealth(name="redis", available=True)
    except ImportError:
        return ComponentHealth(name="redis", available=False, detail="redis client not installed")
    except Exception as error:  # noqa: BLE001
        return ComponentHealth(name="redis", available=False, detail=_redact_error(error))


async def _check_qdrant(settings: Settings) -> ComponentHealth:
    if not settings.rag_enabled:
        return ComponentHealth(name="qdrant", available=False, detail="rag disabled")
    try:
        import httpx

        headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.qdrant_url}/readyz", headers=headers)
        available = response.status_code == 200
        return ComponentHealth(name="qdrant", available=available, detail=None if available else f"status {response.status_code}")
    except Exception as error:  # noqa: BLE001
        return ComponentHealth(name="qdrant", available=False, detail=_redact_error(error))


async def _check_object_store(settings: Settings) -> ComponentHealth:
    if not settings.rag_enabled:
        return ComponentHealth(name="object_store", available=False, detail="rag disabled")
    if settings.object_store_local_path is not None:
        from pathlib import Path

        available = Path(settings.object_store_local_path).exists()
        return ComponentHealth(name="object_store", available=available, detail="local path" if available else "local path missing")
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.object_store_endpoint}/minio/health/live")
        available = response.status_code == 200
        return ComponentHealth(
            name="object_store",
            available=available,
            detail=None if available else f"status {response.status_code}",
        )
    except Exception as error:  # noqa: BLE001
        return ComponentHealth(name="object_store", available=False, detail=_redact_error(error))


@dataclass(frozen=True)
class QdrantRuntimeValidation:
    """Result of validating Qdrant runtime configuration for production safety."""

    valid: bool
    reason: str | None = None

    @classmethod
    def ok(cls) -> "QdrantRuntimeValidation":
        return cls(valid=True)

    @classmethod
    def invalid(cls, reason: str) -> "QdrantRuntimeValidation":
        return cls(valid=False, reason=reason)


def validate_qdrant_runtime_config(settings: Settings) -> QdrantRuntimeValidation:
    """Validate Qdrant runtime configuration against production requirements.

    In production with RAG enabled, Qdrant MUST have an API key and strict
    mode enabled. This is a config-time check — it does not contact Qdrant.
    Payload indexes and snapshots are enforced at collection creation time by
    the ingestion pipeline; this check guards the runtime baseline.
    """
    if not settings.rag_enabled:
        return QdrantRuntimeValidation.ok()
    if settings.rag_runtime_mode == RAG_RUNTIME_PRODUCTION:
        if not settings.qdrant_api_key:
            return QdrantRuntimeValidation.invalid("QDRANT_API_KEY is required in production")
        if not settings.qdrant_strict_mode:
            return QdrantRuntimeValidation.invalid("Qdrant strict mode must be enabled in production")
    return QdrantRuntimeValidation.ok()


async def build_readiness_report(settings: Settings) -> ReadinessReport:
    """Probe each dependency and return a redacted readiness report.

    Liveness is implied ``ok`` because this function ran. Readiness is
    ``ready`` only when every RAG-enabled dependency reports available.
    """
    components: list[ComponentHealth] = []

    if settings.rag_enabled:
        components.append(await _check_postgres(settings))
        components.append(await _check_redis(settings))
        components.append(await _check_qdrant(settings))
        components.append(await _check_object_store(settings))
    else:
        components.append(await _check_postgres(settings))

    all_available = all(c.available for c in components)
    return ReadinessReport(
        status="ready" if all_available else "degraded",
        components=components,
        deployment_tenant_id=settings.deployment_tenant_id,
        rag_enabled=settings.rag_enabled,
        rag_runtime_mode=settings.rag_runtime_mode,
    )
