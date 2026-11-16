"""User-facing wording for connection problems. No model is called: the errors are built by hand."""

import anthropic
import httpx

from gift_genius.errors import describe_error

SECRET = "sk-test-SECRET-123"


def request() -> httpx.Request:
    """A throwaway request object. The anthropic error classes need one to be built."""
    return httpx.Request("POST", "http://model.test/v1/messages")


def test_a_timeout_says_the_model_took_too_long():
    """A slow model is not an unreachable one. The user needs to hear that it took too long,
    because the fix is a faster model, not a network check. Before this change a local model
    that timed out was reported as an unreachable Claude API."""
    message = describe_error(anthropic.APITimeoutError(request=request()))
    assert "took too long" in message


def test_connection_error_does_not_blame_claude():
    """The same wording is shown for Claude, Foundry and Ollama, so it must not name one of them.
    A user running a local Ollama model was told the Claude API could not be reached."""
    message = describe_error(anthropic.APIConnectionError(message="refused", request=request()))
    assert "Claude" not in message
    assert "Could not reach the model service" in message


def test_timeout_and_connection_messages_differ_and_hide_the_raw_text():
    """A timeout is a kind of connection error in the library, so the timeout check has to come
    first or its message is never shown. Raw exception text can echo a secret, so it is never
    included in either message."""
    timeout = describe_error(anthropic.APITimeoutError(request=request()))
    refused = describe_error(anthropic.APIConnectionError(message=SECRET, request=request()))
    assert timeout != refused
    assert SECRET not in timeout and SECRET not in refused
