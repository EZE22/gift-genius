"""User-facing wording for errors that end a search. Shared by every front end."""

from __future__ import annotations

import logging

import anthropic

from .client import ConfigError
from .orchestrator import GiftError

log = logging.getLogger("gift_genius")

GENERIC_MESSAGE = "Something went wrong. Try again in a moment."


def describe_error(error: Exception) -> str:
    """A message that is safe to show: it never includes secrets or raw exception text."""
    if isinstance(error, GiftError):
        return str(error)
    if isinstance(error, ConfigError):
        return "Gift Genius isn't set up to call Claude yet. Add an API key to the .env file."
    if isinstance(error, anthropic.AuthenticationError):
        return "The Claude API key in .env was rejected."
    if isinstance(error, anthropic.NotFoundError):
        return "The model in .env wasn't found. Check the model and ROUTER_MODEL settings."
    if isinstance(error, anthropic.APIConnectionError):
        return "Could not reach the Claude API. Check the connection and try again."
    if isinstance(error, anthropic.APIStatusError):
        return f"The Claude API returned an error ({error.status_code}). Try again in a moment."
    return GENERIC_MESSAGE


def log_failure(error: Exception) -> None:
    """Log why a search ended, without exception text that could hold secrets."""
    if isinstance(error, GiftError):
        log.info("Search stopped: %s", error)
    elif isinstance(error, anthropic.APIStatusError):
        log.warning("Search failed: %s (HTTP %s)", type(error).__name__, error.status_code)
    elif isinstance(error, (anthropic.APIError, ConfigError)):
        log.warning("Search failed: %s", type(error).__name__)
    else:
        log.exception("Search failed")
