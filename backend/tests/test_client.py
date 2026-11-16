"""Model settings from the environment, including ROUTER_MODEL."""

import pytest

from gift_genius import client
from gift_genius.agent import MODEL


def test_no_key_is_a_config_error(clean_env):
    """With no Claude and no Foundry key, make_client refuses to build a client."""
    with pytest.raises(client.ConfigError):
        client.make_client()


def test_claude_api_router_defaults_to_main_model(clean_env):
    """A Claude API key uses the fixed specialist model for both roles, with fallbacks on."""
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key")
    s = client.make_client()
    assert (s.model, s.router_model, s.server_fallbacks) == (MODEL, MODEL, True)


def test_router_model_setting_is_used(clean_env):
    """ROUTER_MODEL replaces only the router's model. The specialists stay on MODEL."""
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key")
    clean_env.setenv("ROUTER_MODEL", "claude-haiku-5-5")
    assert client.make_client().router_model == "claude-haiku-5-5"


def test_empty_router_model_means_main_model(clean_env):
    """A blank ROUTER_MODEL is the same as leaving it unset."""
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key")
    clean_env.setenv("ROUTER_MODEL", "  ")
    assert client.make_client().router_model == MODEL


def test_foundry_uses_the_deployment_for_both(clean_env):
    """Foundry uses the deployment name, turns fallbacks off, and still honors ROUTER_MODEL."""
    clean_env.setenv("ANTHROPIC_FOUNDRY_API_KEY", "test-key")
    clean_env.setenv("ANTHROPIC_FOUNDRY_BASE_URL", "https://example.test/anthropic")
    clean_env.setenv("ANTHROPIC_FOUNDRY_DEPLOYMENT", "my-opus")
    s = client.make_client()
    assert (s.model, s.router_model, s.server_fallbacks) == ("my-opus", "my-opus", False)
    clean_env.setenv("ROUTER_MODEL", "my-haiku")
    assert client.make_client().router_model == "my-haiku"


def test_foundry_needs_a_base_url(clean_env):
    """A Foundry key without a base URL is a config error, not a call to a missing endpoint."""
    clean_env.setenv("ANTHROPIC_FOUNDRY_API_KEY", "test-key")
    with pytest.raises(client.ConfigError):
        client.make_client()


def test_ollama_needs_no_key_and_uses_local_defaults(clean_env):
    """MODEL_SOURCE=ollama builds a client with no API key, aimed at local Ollama,
    with every Claude-only feature switched off. The default model is a small
    non-thinking one: a thinking model made every agent call take minutes on an
    8 GB Mac, and a larger model can still be chosen with OLLAMA_MODEL."""
    clean_env.setenv("MODEL_SOURCE", "ollama")
    s = client.make_client()
    assert str(s.client.base_url).rstrip("/") == "http://localhost:11434"
    default = "qwen3:4b-instruct-2507-q4_K_M"
    assert (s.model, s.router_model) == (default, default)
    assert (s.server_fallbacks, s.claude_features) == (False, False)


def test_root_env_path_points_at_the_repository_root():
    """ROOT_ENV is the repository's .env, three parents up from this package file."""
    from pathlib import Path
    assert client.ROOT_ENV == Path(__file__).resolve().parents[2] / ".env"
