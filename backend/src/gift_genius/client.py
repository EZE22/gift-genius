"""Build the model client and settings from the environment.

Three model sources are supported: the Claude API, Microsoft Foundry, and a local
Ollama model. Every model call in the app goes through the client built here, so
swapping the model source never touches the agent, router or orchestrator code.
"""

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

# Where a local Ollama server listens, and the model we use on it. Both can be
# overridden with environment variables (OLLAMA_BASE_URL, OLLAMA_MODEL). That
# matters in a container: inside a Docker container or a Kubernetes pod,
# "localhost" is the container itself, not the machine that runs Ollama, so the
# address has to be a setting and never a fixed value in the code.
#
# The default model is a small instruct model that does not "think" before it
# answers. A thinking model (such as plain qwen3) wrote thousands of reasoning
# tokens before every agent step. On an 8 GB Mac that took 4 to 5 minutes per
# call and hit the timeout above. This model is about 2.5 GB, so it also fits
# next to other apps. A reader might assume a bigger model is always better
# here: it is not, unless the machine has the memory and the speed for it.
# Set OLLAMA_MODEL to use a different one.
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"

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
    # True for Claude API and Foundry, False for Ollama. When False, the agent and
    # router must not send settings only Claude understands (the effort setting
    # and tool_choice), because Ollama does not support them.
    claude_features: bool


def load_env() -> None:
    """Load the root .env into the environment. Variables already set are kept.

    The real key lives only in that file. `load_dotenv` does not override
    variables that the process already has, so a test or a shell export wins.
    """
    if ROOT_ENV.is_file():
        load_dotenv(ROOT_ENV)
    else:
        load_dotenv()  # searches upward from the current folder


def _make_ollama_settings(router_override: str) -> Settings:
    """Settings for a local Ollama model, with no API key needed.

    Ollama speaks the same Messages API as Claude, so we reuse the Anthropic SDK
    and only change where it connects. The address and model name come from the
    environment, with local defaults, so a container can point at another host.
    """
    # `or` (not a default argument) so that an empty value, such as a blank line in
    # .env or an empty ConfigMap entry, also falls back to the default.
    base_url = os.environ.get("OLLAMA_BASE_URL", "").strip() or DEFAULT_OLLAMA_URL
    model = os.environ.get("OLLAMA_MODEL", "").strip() or DEFAULT_OLLAMA_MODEL
    # Ollama ignores the key, but the SDK refuses to start without one, so we send
    # a dummy value. It is not a secret. A real key is never needed here.
    client = anthropic.Anthropic(base_url=base_url, api_key="ollama", timeout=TIMEOUT, max_retries=MAX_RETRIES)
    # Fallbacks and Claude-only features are both off. The router uses the same
    # model unless ROUTER_MODEL says otherwise.
    return Settings(client, model, router_override or model, False, False)


def make_client() -> Settings:
    """Return the client and models.

    MODEL_SOURCE=ollama selects a local Ollama model and wins over any API key.
    Otherwise Microsoft Foundry is used when ANTHROPIC_FOUNDRY_API_KEY is set,
    and the Claude API when ANTHROPIC_API_KEY is set. ROUTER_MODEL picks the
    router's model; when it is empty or unset the router uses the main model.
    """
    # An empty ROUTER_MODEL means "use whichever model the specialists use".
    router_override = os.environ.get("ROUTER_MODEL", "").strip()
    # Checked first on purpose: someone who chose Ollama must not be sent to a paid
    # API because an old ANTHROPIC_API_KEY is still sitting in their .env.
    if os.environ.get("MODEL_SOURCE", "").strip().lower() == "ollama":
        return _make_ollama_settings(router_override)
    if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"):
        # Foundry identifies the model by deployment name, and it has no
        # server-side refusal fallback, so that flag stays off.
        if not os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL"):
            raise ConfigError("ANTHROPIC_FOUNDRY_BASE_URL is not set. Add your Foundry endpoint to .env.")
        model = os.environ.get("ANTHROPIC_FOUNDRY_DEPLOYMENT", "").strip() or MODEL
        client = anthropic.AnthropicFoundry(timeout=TIMEOUT, max_retries=MAX_RETRIES)
        return Settings(client, model, router_override or model, False, True)
    if os.environ.get("ANTHROPIC_API_KEY"):
        # The Claude API uses the fixed specialist model and may use fallbacks.
        client = anthropic.Anthropic(timeout=TIMEOUT, max_retries=MAX_RETRIES)
        return Settings(client, MODEL, router_override or MODEL, True, True)
    raise ConfigError(
        "No API key found. Copy .env.example to .env and set ANTHROPIC_API_KEY "
        "or the ANTHROPIC_FOUNDRY_* settings."
    )
