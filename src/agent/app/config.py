from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


class Settings(BaseSettings):
    foundry_project_endpoint: HttpUrl
    foundry_model_deployment_name: str = Field(min_length=1)
    mcp_url: HttpUrl = "http://127.0.0.1:8001/mcp"
    port: int = Field(default=8002, ge=1, le=65535)

    model_config = SettingsConfigDict(
        env_file=_find_env_file(Path(__file__).resolve().parent),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
