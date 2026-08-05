from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TENANT_MODE_SINGLE_DEPLOYMENT = "single-deployment"
RAG_RUNTIME_DEVELOPMENT = "development"
RAG_RUNTIME_PRODUCTION = "production"


class Settings(BaseSettings):
    api_port: int = 3001
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:5432/open_grounding"
    jwt_secret: str = "development-only-secret"
    jwt_refresh_secret: str | None = None
    environment: str = "development"

    # --- Tenant configuration -------------------------------------------------
    # Required, immutable deployment tenant identity. Must be a valid UUID string.
    # The operator sets this before first startup; it must never be accepted from
    # a client request, header, path, query parameter, or JWT claim.
    deployment_tenant_id: str | None = None

    # Declared tenant mode. Only "single-deployment" is supported in v1.
    tenant_mode: str = TENANT_MODE_SINGLE_DEPLOYMENT

    # --- RAG platform configuration ------------------------------------------
    # Feature flag: RAG runtime and diagnostics are disabled until explicitly
    # enabled, so existing FastAPI behavior stays unchanged by default.
    rag_enabled: bool = False
    rag_runtime_mode: str = RAG_RUNTIME_DEVELOPMENT

    # Qdrant derived vector store.
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_prefix: str = "rag"
    qdrant_strict_mode: bool = True

    # S3-compatible object store for raw sources and parser artifacts.
    object_store_endpoint: str = "http://127.0.0.1:9100"
    object_store_access_key: str | None = None
    object_store_secret_key: str | None = None
    object_store_bucket: str = "rag-artifacts"
    object_store_region: str = "us-east-1"
    # When set, a local filesystem path is used instead of the S3 endpoint
    # for simple development. Production MUST use a real S3-compatible store.
    object_store_local_path: str | None = None

    # Redis URL for BullMQ worker
    redis_url: str = "redis://127.0.0.1:6379"

    # Secret key for encrypting provider credentials at rest
    # CRITICAL: do not lose this key — credentials cannot be decrypted without it
    # Falls back to jwt_secret if not set (dev only)
    secret_key: str | None = None

    # Embedding provider credentials (set here, profile config in DB)
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    fastembed_cache_dir: str | None = None

    # Active index profile identifier. Profiles are resolved from the catalog;
    # secrets stay in environment configuration and are never persisted.
    rag_active_index_profile_id: str | None = None
    rag_query_embedding_profile_id: str | None = None
    rag_query_sparse_profile_id: str | None = None

    # Provider references for embedding, sparse, reranker, and generation.
    rag_embedding_provider: str | None = None
    rag_embedding_model: str | None = None
    rag_embedding_dimensions: int | None = None
    rag_sparse_provider: str | None = None
    rag_sparse_model: str | None = None
    rag_reranker_provider: str | None = None
    rag_reranker_model: str | None = None
    rag_generation_provider: str | None = None
    rag_generation_model: str | None = None

    rag_query_enabled: bool = False
    rag_query_profile_id: str = "default-v1"
    rag_query_max_message_chars: int = 8_000
    rag_query_max_payload_bytes: int = 16_384
    rag_query_recent_messages: int = 6
    rag_query_requests_per_minute: int = 60
    rag_query_max_concurrency: int = 8
    rag_query_timeout_seconds: float = 30.0
    rag_retrieval_timeout_seconds: float = 8.0
    rag_generation_timeout_seconds: float = 20.0
    rag_retrieval_dense_candidates: int = 50
    rag_retrieval_sparse_candidates: int = 50
    rag_retrieval_fused_candidates: int = 40
    rag_retrieval_reranker_candidates: int = 24
    rag_context_max_chunks: int = 12
    rag_context_token_budget: int = 8_000
    rag_generation_max_output_tokens: int = 1_024
    rag_query_trace_retention_days: int = 30
    rag_query_max_retrieval_retries: int = 1
    rag_query_max_validation_repairs: int = 1

    # --- Ingestion pipeline configuration -------------------------------------
    # Supported MIME types for v1 source intake. Unsupported types are rejected.
    rag_ingestion_supported_mime_types: str = "application/pdf,text/markdown,text/plain,text/x-markdown,application/markdown"
    # Maximum source file size in bytes (default 50 MB).
    rag_ingestion_max_file_size_bytes: int = 52_428_800
    # Maximum page count for PDF sources.
    rag_ingestion_max_pages: int = 500
    # Malware-scan mode: "required" (production) or "development-bypass" (dev).
    rag_ingestion_malware_scan_mode: str = "development-bypass"
    # Token budgets for structure-aware parent-child chunking.
    rag_ingestion_child_token_min: int = 300
    rag_ingestion_child_token_max: int = 500
    rag_ingestion_child_token_hard_max: int = 700
    rag_ingestion_parent_token_min: int = 1000
    rag_ingestion_parent_token_max: int = 2000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("deployment_tenant_id")
    @classmethod
    def validate_deployment_tenant_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        # Validate UUID format at config-load time so malformed values fail fast.
        from uuid import UUID

        try:
            UUID(stripped)
        except (ValueError, TypeError) as error:
            raise ValueError("DEPLOYMENT_TENANT_ID must be a valid UUID string") from error
        return stripped

    @field_validator("tenant_mode")
    @classmethod
    def validate_tenant_mode(cls, value: str) -> str:
        if value != TENANT_MODE_SINGLE_DEPLOYMENT:
            raise ValueError(f"Unsupported tenant mode '{value}'. Only '{TENANT_MODE_SINGLE_DEPLOYMENT}' is supported.")
        return value

    @field_validator("rag_runtime_mode")
    @classmethod
    def validate_rag_runtime_mode(cls, value: str) -> str:
        if value not in (RAG_RUNTIME_DEVELOPMENT, RAG_RUNTIME_PRODUCTION):
            raise ValueError(f"Unsupported RAG runtime mode '{value}'. Only '{RAG_RUNTIME_DEVELOPMENT}' or '{RAG_RUNTIME_PRODUCTION}' is supported.")
        return value

    @field_validator("rag_ingestion_malware_scan_mode")
    @classmethod
    def validate_malware_scan_mode(cls, value: str) -> str:
        if value not in ("required", "development-bypass"):
            raise ValueError(f"Unsupported malware-scan mode '{value}'. Only 'required' or 'development-bypass' is supported.")
        return value

    @field_validator(
        "rag_query_max_message_chars", "rag_query_max_payload_bytes", "rag_query_recent_messages",
        "rag_query_requests_per_minute", "rag_query_max_concurrency", "rag_retrieval_dense_candidates",
        "rag_retrieval_sparse_candidates", "rag_retrieval_fused_candidates", "rag_retrieval_reranker_candidates",
        "rag_context_max_chunks", "rag_context_token_budget", "rag_generation_max_output_tokens",
        "rag_query_trace_retention_days",
    )
    @classmethod
    def validate_positive_query_budget(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RAG query budgets and limits must be greater than zero")
        return value

    @field_validator("rag_query_timeout_seconds", "rag_retrieval_timeout_seconds", "rag_generation_timeout_seconds")
    @classmethod
    def validate_positive_query_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("RAG query timeouts must be greater than zero")
        return value

    @field_validator("rag_query_max_retrieval_retries", "rag_query_max_validation_repairs")
    @classmethod
    def validate_bounded_query_retry(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("RAG query retry and repair limits must be zero or one")
        return value

    @model_validator(mode="after")
    def validate_rag_production_secrets(self) -> "Settings":
        """In production runtime mode with RAG enabled, Qdrant API key and
        object-store credentials MUST be set. Development permits defaults."""
        if self.rag_enabled and self.rag_runtime_mode == RAG_RUNTIME_PRODUCTION:
            if not self.qdrant_api_key:
                raise ValueError("QDRANT_API_KEY is required when RAG is enabled in production")
            if not self.object_store_access_key or not self.object_store_secret_key:
                raise ValueError("OBJECT_STORE_ACCESS_KEY and OBJECT_STORE_SECRET_KEY are required when RAG is enabled in production")
        if self.rag_retrieval_fused_candidates > self.rag_retrieval_dense_candidates + self.rag_retrieval_sparse_candidates:
            raise ValueError("RAG_RETRIEVAL_FUSED_CANDIDATES cannot exceed combined retrieval candidates")
        if self.rag_retrieval_reranker_candidates > self.rag_retrieval_fused_candidates:
            raise ValueError("RAG_RETRIEVAL_RERANKER_CANDIDATES cannot exceed fused candidates")
        return self

    @property
    def ingestion_supported_mime_types_set(self) -> frozenset[str]:
        """Return supported MIME types as a set for fast membership checks."""
        return frozenset(m.strip() for m in self.rag_ingestion_supported_mime_types.split(",") if m.strip())

    @property
    def async_database_url(self) -> str:
        base_url = self.database_url.split("?", maxsplit=1)[0]
        return base_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def refresh_secret(self) -> str:
        return self.jwt_refresh_secret or self.jwt_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
