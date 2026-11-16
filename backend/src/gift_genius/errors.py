"""User-facing wording for errors that end a search. Shared by every front end."""

from __future__ import annotations

import logging

import anthropic

from .client import ConfigError
from .orchestrator import GiftError

log = logging.getLogger("gift_genius")

GENERIC_MESSAGE = "Something went wrong. Try again in a moment."


def describe_error(error: Exception) -> str:
    """A message that is safe to show: it never includes secrets or raw exception text.

    GiftError is the one case whose own text is shown, because this code wrote
    it. Every other branch uses a fixed sentence. The HTTP status is included
    for API errors; the response body is not, because a provider message can
    echo part of a request.
    """
    if isinstance(error, GiftError):
        return str(error)
    if isinstance(error, ConfigError):
        return "Gift Genius isn't set up to call Claude yet. Add an API key to the .env file."
    if isinstance(error, anthropic.AuthenticationError):
        return "The Claude API key in .env was rejected."
    if isinstance(error, anthropic.NotFoundError):
        return "The model in .env wasn't found. Check the model and ROUTER_MODEL settings."
    # The timeout check must come first. In the anthropic library a timeout is a
    # kind of connection error, so the check below would catch it and the user
    # would be told the server is unreachable when it was only slow. The wording
    # names no provider because the same sentence is shown for Claude, Foundry
    # and a local Ollama model.
    if isinstance(error, anthropic.APITimeoutError):
        return "The model took too long to answer. Try again, or use a smaller or faster model."
    if isinstance(error, anthropic.APIConnectionError):
        return "Could not reach the model service. Check that it is running and try again."
    if isinstance(error, anthropic.APIStatusError):
        return f"The Claude API returned an error ({error.status_code}). Try again in a moment."
    return GENERIC_MESSAGE


def log_failure(error: Exception) -> None:
    """Log why a search ended, without exception text that could hold secrets.

    Known API and config failures log only the exception type (and status
    code). An unexpected error uses log.exception so the traceback is kept
    for debugging; that path is the one place a message might include a secret,
    and it stays in the server log, never in the response.
    """
    if isinstance(error, GiftError):
        log.info("Search stopped: %s", error)
    elif isinstance(error, anthropic.APIStatusError):
        log.warning("Search failed: %s (HTTP %s)", type(error).__name__, error.status_code)
    elif isinstance(error, (anthropic.APIError, ConfigError)):
        log.warning("Search failed: %s", type(error).__name__)
    else:
        log.exception("Search failed")
