from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


class Settings(BaseSettings):
    copilot_auth_mode: Literal["local", "pat"] = "local"
    copilot_model: str = Field(default="auto", min_length=1)
    copilot_github_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    mcp_url: HttpUrl = "http://127.0.0.1:8001/mcp"
    port: int = Field(default=8002, ge=1, le=65535)

    model_config = SettingsConfigDict(
        env_file=_find_env_file(Path(__file__).resolve().parent),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    @field_validator("copilot_model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("COPILOT_MODEL must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_auth(self) -> "Settings":
        if self.copilot_auth_mode == "pat" and (
            self.copilot_github_token is None
            or not self.copilot_github_token.get_secret_value().strip()
        ):
            raise ValueError("COPILOT_GITHUB_TOKEN is required for pat authentication.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
