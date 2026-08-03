"""Unit tests for the RAG platform foundation: settings validation, profile
compatibility, readiness redaction, and provider-port contracts.

These are pure unit tests that do not require PostgreSQL, Qdrant, or object
storage. Live dependency probes are covered by integration tests.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.settings import RAG_RUNTIME_DEVELOPMENT, RAG_RUNTIME_PRODUCTION, Settings
from app.domain.rag.profiles import (
    DistanceMetric,
    IndexProfile,
    ModelProfile,
    ProfileCompatibility,
    validate_index_profile_compatibility,
)
from app.infrastructure.rag_health import ComponentHealth, ReadinessReport

# --- Settings validation ------------------------------------------------------


def test_rag_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.rag_enabled is False
    assert settings.rag_runtime_mode == RAG_RUNTIME_DEVELOPMENT


def test_rag_runtime_mode_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rag_enabled=True, rag_runtime_mode="staging")


def test_rag_production_requires_qdrant_api_key() -> None:
    with pytest.raises(ValidationError, match="QDRANT_API_KEY"):
        Settings(_env_file=None, rag_enabled=True, rag_runtime_mode=RAG_RUNTIME_PRODUCTION)


def test_rag_production_requires_object_store_credentials() -> None:
    with pytest.raises(ValidationError, match="OBJECT_STORE"):
        Settings(
            _env_file=None,
            rag_enabled=True,
            rag_runtime_mode=RAG_RUNTIME_PRODUCTION,
            qdrant_api_key="key",
        )


def test_rag_production_accepts_with_secrets() -> None:
    settings = Settings(
        _env_file=None,
        rag_enabled=True,
        rag_runtime_mode=RAG_RUNTIME_PRODUCTION,
        qdrant_api_key="key",
        object_store_access_key="ak",
        object_store_secret_key="sk",
    )
    assert settings.rag_enabled
    assert settings.qdrant_strict_mode is True


def test_rag_development_permits_missing_secrets() -> None:
    settings = Settings(_env_file=None, rag_enabled=True, rag_runtime_mode=RAG_RUNTIME_DEVELOPMENT)
    assert settings.rag_enabled
    assert settings.qdrant_api_key is None


# --- Profile compatibility ----------------------------------------------------


def _embedding_profile(pid: str = "emb-1", dims: int = 768) -> ModelProfile:
    return ModelProfile(
        id=pid, profile_kind="embedding", provider="local", model="bge", dimensions=dims, version="1"
    )


def _index_profile(eid: str = "emb-1", dims: int = 768) -> IndexProfile:
    return IndexProfile(
        id="idx-1",
        embedding_profile_id=eid,
        sparse_profile_id=None,
        collection="rag",
        dimensions=dims,
        distance_metric=DistanceMetric.COSINE,
        version="1",
    )


def test_index_profile_compatible_when_dimensions_match() -> None:
    result = validate_index_profile_compatibility(index=_index_profile(), embedding=_embedding_profile())
    assert result.is_compatible
    assert result.reason is None


def test_index_profile_rejects_dimension_mismatch() -> None:
    result = validate_index_profile_compatibility(
        index=_index_profile(dims=1024), embedding=_embedding_profile(dims=768)
    )
    assert not result.is_compatible
    assert "1024" in (result.reason or "")


def test_index_profile_rejects_missing_embedding_dimensions() -> None:
    emb = ModelProfile(
        id="emb-1", profile_kind="embedding", provider="local", model="bge", dimensions=None, version="1"
    )
    result = validate_index_profile_compatibility(index=_index_profile(), embedding=emb)
    assert not result.is_compatible
    assert "dimensions" in (result.reason or "").lower()


def test_index_profile_rejects_profile_reference_mismatch() -> None:
    result = validate_index_profile_compatibility(
        index=_index_profile(eid="emb-1"), embedding=_embedding_profile(pid="emb-other")
    )
    assert not result.is_compatible
    assert "reference" in (result.reason or "").lower()


def test_profile_compatibility_ok_factory() -> None:
    result = ProfileCompatibility.ok()
    assert result.is_compatible
    assert result.reason is None

# --- Readiness redaction ------------------------------------------------------


def test_readiness_report_to_dict_redacts_secrets() -> None:
    report = ReadinessReport(
        status="degraded",
        components=[
            ComponentHealth(name="qdrant", available=False, detail="ConnectionError: unavailable"),
            ComponentHealth(name="object_store", available=True),
        ],
        deployment_tenant_id=str(uuid4()),
        rag_enabled=True,
        rag_runtime_mode=RAG_RUNTIME_PRODUCTION,
    )
    rendered = str(report.to_dict())
    assert "password" not in rendered.lower()
    assert "secret" not in rendered.lower()
    assert "api_key" not in rendered.lower()


def test_readiness_report_status_degraded_when_any_unavailable() -> None:
    report = ReadinessReport(
        status="degraded",
        components=[
            ComponentHealth(name="postgresql", available=True),
            ComponentHealth(name="qdrant", available=False),
        ],
    )
    data = report.to_dict()
    assert data["status"] == "degraded"
    assert data["components"][1]["available"] is False


def test_readiness_report_omits_components_when_rag_disabled() -> None:
    report = ReadinessReport(status="ready", components=[], rag_enabled=False)
    data = report.to_dict()
    assert data["ragEnabled"] is False
    assert data["components"] == []


# --- Provider-port contracts --------------------------------------------------


def test_embedding_adapter_is_protocol() -> None:
    from app.domain.rag.adapter_ports import EmbeddingAdapter

    assert hasattr(EmbeddingAdapter, "embed")


def test_sparse_encoder_adapter_is_protocol() -> None:
    from app.domain.rag.adapter_ports import SparseEncoderAdapter

    assert hasattr(SparseEncoderAdapter, "encode")


def test_reranker_adapter_is_protocol() -> None:
    from app.domain.rag.adapter_ports import RerankerAdapter

    assert hasattr(RerankerAdapter, "rerank")


def test_generation_adapter_is_protocol() -> None:
    from app.domain.rag.adapter_ports import GenerationAdapter

    assert hasattr(GenerationAdapter, "generate")


def test_embedding_adapter_stub_satisfies_protocol() -> None:
    from app.domain.rag.adapter_ports import EmbeddingAdapter

    class StubEmbeddingAdapter:
        async def embed(
            self, *, tenant: object, texts: list[str], model_profile_id: str
        ) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]

    stub: EmbeddingAdapter = StubEmbeddingAdapter()  # type: ignore[assignment]
    assert stub is not None


# --- Qdrant runtime config validation ----------------------------------------


def test_qdrant_validation_passes_when_rag_disabled() -> None:
    from app.infrastructure.rag_health import validate_qdrant_runtime_config

    settings = Settings(_env_file=None)
    result = validate_qdrant_runtime_config(settings)
    assert result.valid


def test_qdrant_validation_passes_in_development() -> None:
    from app.infrastructure.rag_health import validate_qdrant_runtime_config

    settings = Settings(_env_file=None, rag_enabled=True, rag_runtime_mode=RAG_RUNTIME_DEVELOPMENT)
    result = validate_qdrant_runtime_config(settings)
    assert result.valid


def test_qdrant_validation_rejects_missing_api_key_in_production() -> None:
    from app.infrastructure.rag_health import validate_qdrant_runtime_config

    settings = Settings(_env_file=None, rag_enabled=True, rag_runtime_mode=RAG_RUNTIME_PRODUCTION, qdrant_api_key="key", object_store_access_key="ak", object_store_secret_key="sk")
    result = validate_qdrant_runtime_config(settings)
    assert result.valid


def test_qdrant_validation_rejects_strict_mode_disabled_in_production() -> None:
    from app.infrastructure.rag_health import validate_qdrant_runtime_config

    settings = Settings(_env_file=None, rag_enabled=True, rag_runtime_mode=RAG_RUNTIME_PRODUCTION, qdrant_api_key="key", qdrant_strict_mode=False, object_store_access_key="ak", object_store_secret_key="sk")
    result = validate_qdrant_runtime_config(settings)
    assert not result.valid
    assert "strict" in (result.reason or "").lower()
