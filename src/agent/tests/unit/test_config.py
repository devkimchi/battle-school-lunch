import pytest

from app.config import Settings


@pytest.mark.unit
def test_accepts_aspire_foundry_deployment_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/test",
    )
    monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT", "foundry-model")

    settings = Settings(_env_file=None)

    assert settings.foundry_model_deployment_name == "foundry-model"
