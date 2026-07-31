from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_port: int = 3001
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:5432/vibecoding_starter"
    jwt_secret: str = "development-only-secret"
    jwt_refresh_secret: str | None = None
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
