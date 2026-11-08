import pytest

API_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_FOUNDRY_API_KEY",
    "ANTHROPIC_FOUNDRY_BASE_URL",
    "ANTHROPIC_FOUNDRY_DEPLOYMENT",
    "ANTHROPIC_FOUNDRY_RESOURCE",
    "ROUTER_MODEL",
]


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all API settings from the environment for the test."""
    for name in API_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch
