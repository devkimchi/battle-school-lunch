import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("COPILOT_AUTH_MODE", "COPILOT_MODEL", "COPILOT_GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_do_not_require_foundry_or_pat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_URI", "ignored")
    monkeypatch.setenv("FOUNDRY_MODEL_MODELNAME", "ignored")
    settings = Settings(_env_file=None)
    assert settings.copilot_auth_mode == "local"
    assert settings.copilot_model == "auto"
    assert settings.copilot_github_token is None
    assert not any("foundry" in name for name in Settings.model_fields)
    assert str(settings.mcp_url) == "http://127.0.0.1:8001/mcp"
    assert settings.port == 8002


def test_pat_environment_and_secret_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_AUTH_MODE", "pat")
    monkeypatch.setenv("COPILOT_MODEL", "test-model")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "fake-private-token")
    settings = Settings(_env_file=None)
    assert settings.copilot_auth_mode == "pat"
    assert settings.copilot_model == "test-model"
    assert isinstance(settings.copilot_github_token, SecretStr)
    assert settings.copilot_github_token.get_secret_value() == "fake-private-token"
    assert "fake-private-token" not in repr(settings)
    assert "copilot_github_token" not in settings.model_dump()
    assert "fake-private-token" not in settings.model_dump_json()


@pytest.mark.parametrize("token", [None, "", " \t\n"])
def test_pat_requires_nonblank_explicit_token(token: str | None) -> None:
    with pytest.raises(ValidationError, match="COPILOT_GITHUB_TOKEN is required"):
        Settings(_env_file=None, copilot_auth_mode="pat", copilot_github_token=token)


@pytest.mark.parametrize("model", ["", " \t\n"])
def test_rejects_blank_model(model: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, copilot_model=model)


@pytest.mark.parametrize("mode", ["", "azure", "PAT"])
def test_rejects_unknown_auth_mode(mode: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, copilot_auth_mode=mode)


def test_validation_error_does_not_display_token() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None, copilot_auth_mode="invalid",
            copilot_github_token="fake-private-token",
        )
    assert "fake-private-token" not in str(exc.value)
