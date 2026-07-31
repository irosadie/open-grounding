from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TENANT_MODE_SINGLE_DEPLOYMENT = "single-deployment"


class Settings(BaseSettings):
    api_port: int = 3001
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:5432/vibecoding_starter"
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
            raise ValueError(
                f"Unsupported tenant mode '{value}'. Only '{TENANT_MODE_SINGLE_DEPLOYMENT}' is supported."
            )
        return value

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
