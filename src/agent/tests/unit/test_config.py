import pytest

from app.config import Settings


@pytest.mark.unit
def test_accepts_aspire_foundry_deployment_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_MODEL_DEPLOYMENT_NAME",
        "FOUNDRY_MODEL_DEPLOYMENT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_URI",
        "https://example.services.ai.azure.com/api/projects/test",
    )
    monkeypatch.setenv("FOUNDRY_MODEL_MODELNAME", "foundry-model")

    settings = Settings(_env_file=None)

    assert str(settings.foundry_project_endpoint) == (
        "https://example.services.ai.azure.com/api/projects/test"
    )
    assert settings.foundry_model_deployment_name == "foundry-model"


@pytest.mark.unit
def test_accepts_compose_foundry_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("FOUNDRY_PROJECT_URI", "FOUNDRY_MODEL_MODELNAME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/test",
    )
    monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "foundry-model")

    settings = Settings(_env_file=None)

    assert settings.foundry_model_deployment_name == "foundry-model"
