"""Model settings from the environment, including ROUTER_MODEL."""

import pytest

from gift_genius import client
from gift_genius.agent import MODEL


def test_no_key_is_a_config_error(clean_env):
    with pytest.raises(client.ConfigError):
        client.make_client()


def test_claude_api_router_defaults_to_main_model(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key")
    s = client.make_client()
    assert (s.model, s.router_model, s.server_fallbacks) == (MODEL, MODEL, True)


def test_router_model_setting_is_used(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key")
    clean_env.setenv("ROUTER_MODEL", "claude-haiku-5-5")
    assert client.make_client().router_model == "claude-haiku-5-5"


def test_empty_router_model_means_main_model(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key")
    clean_env.setenv("ROUTER_MODEL", "  ")
    assert client.make_client().router_model == MODEL


def test_foundry_uses_the_deployment_for_both(clean_env):
    clean_env.setenv("ANTHROPIC_FOUNDRY_API_KEY", "test-key")
    clean_env.setenv("ANTHROPIC_FOUNDRY_BASE_URL", "https://example.test/anthropic")
    clean_env.setenv("ANTHROPIC_FOUNDRY_DEPLOYMENT", "my-opus")
    s = client.make_client()
    assert (s.model, s.router_model, s.server_fallbacks) == ("my-opus", "my-opus", False)
    clean_env.setenv("ROUTER_MODEL", "my-haiku")
    assert client.make_client().router_model == "my-haiku"


def test_foundry_needs_a_base_url(clean_env):
    clean_env.setenv("ANTHROPIC_FOUNDRY_API_KEY", "test-key")
    with pytest.raises(client.ConfigError):
        client.make_client()


def test_root_env_path_points_at_the_repository_root():
    from pathlib import Path
    assert client.ROOT_ENV == Path(__file__).resolve().parents[2] / ".env"
