"""A generic agentic loop for the Claude Messages API.

This module knows nothing about gifts or the catalog. The caller supplies a
system prompt, a first message, tool schemas, a function that runs tools, a
tool call cap and, optionally, a check that can reject the final text.

Each loop: ask the model; if it calls tools, run them (up to the cap) and send
the results back; once the cap is reached, the next request forbids tools
(tool_choice "none") so the model must answer in text. When the model answers
in text, the optional check may return a correction message, which is sent
back and the loop continues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000  # includes the model's thinking, so keep generous
EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

DEFAULT_CAP_MESSAGE = "You have used all {cap} tool calls. Write your final answer now."


class AgentError(Exception):
    """Base class for loop failures."""


class AgentRefused(AgentError):
    """The model declined (stop_reason "refusal")."""


class AgentOutOfTokens(AgentError):
    """The model hit max_tokens before finishing."""


class AgentDidNotFinish(AgentError):
    """The loop used all its requests without an accepted answer."""


class AgentStoppedEarly(AgentError):
    """The model stopped for a reason the loop doesn't expect (e.g. the context window filled)."""

    def __init__(self, stop_reason):
        super().__init__(f"unexpected stop_reason {stop_reason!r}")
        self.stop_reason = stop_reason


# Stop reasons that mean "here is a finished answer"; "tool_use" means "run these tools".
FINISHED = {"end_turn", "stop_sequence"}


@dataclass
class ToolCall:
    name: str
    input: dict
    content: str
    is_error: bool


@dataclass
class AgentResult:
    text: str
    tool_calls: list[ToolCall]


# run_tool(name, input) -> (result_text, is_error)
RunTool = Callable[[str, dict], "tuple[str, bool]"]
# check(final_text, tool_calls) -> None to accept, or a correction message
Check = Callable[[str, "list[ToolCall]"], Optional[str]]


def _create(client, model: str, server_fallbacks: bool, params: dict):
    """Send one Messages API request and return the whole reply.

    On the Claude API, the beta endpoint can swap in a fallback model if this
    one refuses. Foundry does not support that header, so those calls use the
    plain endpoint.
    """
    if server_fallbacks:
        # Server-side refusal fallback: Claude API only, not Microsoft Foundry.
        return client.beta.messages.create(
            model=model, **params, betas=[FALLBACK_BETA], fallbacks="default"
        )
    return client.messages.create(model=model, **params)


def run_agent(
    client,
    *,
    system: str,
    first_message: str,
    tools: list[dict],
    run_tool: RunTool,
    max_tool_calls: int,
    check: Optional[Check] = None,
    model: str = MODEL,
    server_fallbacks: bool = True,
    max_requests: Optional[int] = None,
    cap_message: str = DEFAULT_CAP_MESSAGE,
    on_request: Optional[Callable[[], None]] = None,
    on_tool_call: Optional[Callable[[str, dict], None]] = None,
) -> AgentResult:
    """Run the loop until the model gives a text answer the check accepts.

    on_request() is called before each model request; on_tool_call(name, input)
    just before each tool runs. Exceptions raised by run_tool, check or the
    callbacks propagate unchanged.
    """
    if max_requests is None:
        # A few extra turns past the tool cap: one to force the text answer,
        # plus room for a check to send the answer back.
        max_requests = max_tool_calls + 5
    # The transcript starts as one user turn. Every later model reply and tool
    # result is appended here and sent back on the next request.
    messages: list = [{"role": "user", "content": first_message}]
    calls: list[ToolCall] = []

    for _ in range(max_requests):
        # Spent the tool budget: the next request must answer in text.
        force_text = len(calls) >= max_tool_calls
        if on_request:
            on_request()
        params = dict(
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            tools=tools,
            # Opus 5.5 rejects forced tool use; "none" (no tools) is allowed and
            # is how we force a text answer once the tool budget is spent.
            tool_choice={"type": "none"} if force_text else {"type": "auto"},
            output_config={"effort": EFFORT},
        )
        response = _create(client, model, server_fallbacks, params)

        # These stop reasons are failures. A max_tokens reply can still contain
        # a tool call, but it is unfinished, so the loop never runs that tool.
        if response.stop_reason == "refusal":
            raise AgentRefused()
        if response.stop_reason == "max_tokens":
            raise AgentOutOfTokens()

        # Append the full content (thinking and tool_use blocks included), unchanged.
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            continue  # the server paused a long turn; sending it back resumes it
        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses and response.stop_reason not in FINISHED:
            # Never treat a reply cut off for an unknown reason as the final answer.
            raise AgentStoppedEarly(response.stop_reason)

        if tool_uses:
            # One reply can ask for several tools. Run the ones still under the
            # cap, and answer the rest with an error so every tool_use id has a
            # matching tool_result (the API requires that).
            results: list = []
            for block in tool_uses:
                if len(calls) >= max_tool_calls:
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Not run: the limit of {max_tool_calls} tool calls is reached.",
                            "is_error": True,
                        }
                    )
                    continue
                if on_tool_call:
                    on_tool_call(block.name, block.input)
                content, is_error = run_tool(block.name, block.input)
                calls.append(ToolCall(block.name, block.input, content, is_error))
                result = {"type": "tool_result", "tool_use_id": block.id, "content": content}
                if is_error:
                    result["is_error"] = True
                results.append(result)
            if len(calls) >= max_tool_calls:
                # Sit next to the tool results so the model sees the cap before
                # the following request, which will set tool_choice to "none".
                results.append({"type": "text", "text": cap_message.format(cap=max_tool_calls)})
            # All results go back in one user message, matching each tool_use id.
            messages.append({"role": "user", "content": results})
            continue

        # No tools in this reply: treat the text blocks as the candidate answer.
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
        correction = check(text, calls) if check else None
        if correction is None:
            return AgentResult(text, calls)
        # The check rejected the text. Send its message back as the next user
        # turn and let the model try again, still inside this same loop.
        messages.append({"role": "user", "content": correction})

    raise AgentDidNotFinish()
