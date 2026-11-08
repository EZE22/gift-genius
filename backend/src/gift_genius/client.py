"""Build the Claude client and model settings from the root .env (Claude API or Microsoft Foundry)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from .agent import MODEL

# A request returns only once the whole reply is written (no streaming), so the
# read timeout must cover a full reply. One retry keeps a stalled network short.
TIMEOUT = anthropic.Timeout(300.0, connect=10.0)
MAX_RETRIES = 1

# backend/src/gift_genius/client.py -> the repository root
ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class ConfigError(Exception):
    """The environment has no usable API settings."""


@dataclass
class Settings:
    client: object
    model: str  # the specialists' model
    router_model: str  # the fast model for the one-label router call
    server_fallbacks: bool  # server-side refusal fallback (Claude API only)


def load_env() -> None:
    """Load the root .env into the environment. Variables already set are kept."""
    if ROOT_ENV.is_file():
        load_dotenv(ROOT_ENV)
    else:
        load_dotenv()  # searches upward from the current folder


def make_client() -> Settings:
    """Return the client and models.

    Microsoft Foundry is used when ANTHROPIC_FOUNDRY_API_KEY is set; otherwise
    the Claude API with ANTHROPIC_API_KEY. ROUTER_MODEL picks the router's model;
    when it is empty or unset the router uses the main model.
    """
    router_override = os.environ.get("ROUTER_MODEL", "").strip()
    if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"):
        if not os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL"):
            raise ConfigError("ANTHROPIC_FOUNDRY_BASE_URL is not set. Add your Foundry endpoint to .env.")
        model = os.environ.get("ANTHROPIC_FOUNDRY_DEPLOYMENT", "").strip() or MODEL
        client = anthropic.AnthropicFoundry(timeout=TIMEOUT, max_retries=MAX_RETRIES)
        return Settings(client, model, router_override or model, False)
    if os.environ.get("ANTHROPIC_API_KEY"):
        client = anthropic.Anthropic(timeout=TIMEOUT, max_retries=MAX_RETRIES)
        return Settings(client, MODEL, router_override or MODEL, True)
    raise ConfigError(
        "No API key found. Copy .env.example to .env and set ANTHROPIC_API_KEY "
        "or the ANTHROPIC_FOUNDRY_* settings."
    )
