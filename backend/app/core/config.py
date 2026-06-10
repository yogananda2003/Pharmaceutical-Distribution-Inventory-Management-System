from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Pharma Distribution & Inventory Management System"
    environment: str = "development"
    debug: bool = True

    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pharma_dev"

    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:5173"]

    rate_limit_login: str = "5/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
