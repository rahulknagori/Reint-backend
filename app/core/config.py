from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "SMAI Backend"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    api_v1_prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = Field(default=["http://localhost:5173"])
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@db:5432/smai_backend"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
