"""Tests for the generic agentic loop, using a fake calculator tool.

Nothing here knows about debates or Wikipedia: the loop is exercised with an
"add" tool and a scripted client.
"""

import pytest

from gift_genius import agent
from gift_genius.agent import (
    AgentDidNotFinish,
    AgentOutOfTokens,
    AgentRefused,
    AgentStoppedEarly,
    ToolCall,
    run_agent,
)
from fakes import ScriptedClient, resp, text, tool, tool_results

ADD_TOOL = {
    "name": "add",
    "description": "Add two integers. Call this for any arithmetic.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    },
}


def add(a, b, id):
    """One scripted call of the fake add tool."""
    return tool("add", {"a": a, "b": b}, id)


class Calculator:
    """run_tool implementation that records what it was asked to do."""

    def __init__(self):
        self.calls = []

    def __call__(self, name, tool_input):
        self.calls.append((name, tool_input))
        if name != "add":
            return f"unknown tool {name}", True
        return str(tool_input["a"] + tool_input["b"]), False


def run(client, calculator=None, **kwargs):
    """Run the loop with the calculator prompt. kwargs override one option at a time."""
    options = dict(
        system="You are a careful calculator.",
        first_message="What is 2 + 3, plus 4?",
        tools=[ADD_TOOL],
        run_tool=calculator or Calculator(),
        max_tool_calls=3,
        model="test-model",
        server_fallbacks=False,
    )
    options.update(kwargs)
    return run_agent(client, **options)


def test_answers_directly_when_no_tool_is_needed():
    """A text reply with no tool call is the answer, after surrounding whitespace is stripped."""
    client = ScriptedClient([resp(text("Nine."))])
    result = run(client)

    assert result.text == "Nine."
    assert result.tool_calls == []
    assert len(client.requests) == 1


def test_runs_tools_until_the_model_answers():
    """Each tool_use is run, its result is sent back, and the later text is the answer."""
    calc = Calculator()
    client = ScriptedClient([resp(add(2, 3, "t1")), resp(add(5, 4, "t2")), resp(text("  9  "))])
    result = run(client, calc)

    assert result.text == "9"
    assert calc.calls == [("add", {"a": 2, "b": 3}), ("add", {"a": 5, "b": 4})]
    assert result.tool_calls == [
        ToolCall("add", {"a": 2, "b": 3}, "5", False),
        ToolCall("add", {"a": 5, "b": 4}, "9", False),
    ]
    second = client.requests[1][1]
    assert tool_results(second) == [{"type": "tool_result", "tool_use_id": "t1", "content": "5"}]
    # The assistant turn is appended unchanged, thinking block included.
    assert [b.type for b in second["messages"][-2]["content"]] == ["thinking", "tool_use"]


def test_request_shape():
    """The first request carries the prompt, tools, auto tool choice, and no beta headers."""
    client = ScriptedClient([resp(text("ok"))])
    run(client)
    api, request = client.requests[0]

    assert api == "plain"
    assert request["model"] == "test-model"
    assert request["system"] == "You are a careful calculator."
    assert request["messages"] == [{"role": "user", "content": "What is 2 + 3, plus 4?"}]
    assert request["tools"] == [ADD_TOOL]
    assert request["tool_choice"] == {"type": "auto"}
    assert request["max_tokens"] == agent.MAX_TOKENS
    assert request["output_config"] == {"effort": agent.EFFORT}
    assert "betas" not in request and "fallbacks" not in request


def test_without_claude_features_the_request_has_no_claude_only_settings():
    """Ollama does not understand tool_choice or output_config, so with claude_features
    off neither is sent. The tools and the rest of the request stay the same."""
    client = ScriptedClient([resp(text("ok"))])
    run(client, claude_features=False)
    _, request = client.requests[0]
    assert "tool_choice" not in request
    assert "output_config" not in request
    assert request["tools"] == [ADD_TOOL]


def test_server_fallbacks_use_the_beta_api():
    """server_fallbacks switches the call onto the beta endpoint with the fallback header."""
    client = ScriptedClient([resp(text("ok"))])
    run(client, server_fallbacks=True)
    api, request = client.requests[0]

    assert api == "beta"
    assert request["betas"] == [agent.FALLBACK_BETA]
    assert request["fallbacks"] == "default"


def test_parallel_calls_are_answered_in_one_message():
    """Several tool calls in one reply are all answered in the next single user message."""
    client = ScriptedClient([resp(add(1, 1, "a"), add(2, 2, "b")), resp(text("done"))])
    result = run(client)

    assert len(result.tool_calls) == 2
    results = tool_results(client.requests[1][1])
    assert [(r["tool_use_id"], r["content"]) for r in results] == [("a", "2"), ("b", "4")]


def test_tool_errors_are_flagged():
    """A tool that returns is_error=True is recorded, and the API result is marked is_error."""
    client = ScriptedClient([resp(tool("divide", {"a": 1}, "x")), resp(text("can't"))])
    result = run(client)

    assert result.tool_calls[0].is_error is True
    assert tool_results(client.requests[1][1])[0]["is_error"] is True


def test_cap_forbids_tools_and_forces_a_text_answer():
    """After the cap, the next request sets tool_choice to none and tells the model to answer."""
    def model(kwargs):
        if kwargs["tool_choice"]["type"] == "none":
            return resp(text("best guess"))
        n = len(client.requests)
        return resp(add(n, n, f"t{n}"))

    calc = Calculator()
    client = ScriptedClient([model] * 10)
    result = run(client, calc, max_tool_calls=3)

    assert len(calc.calls) == 3
    assert [r["tool_choice"]["type"] for _, r in client.requests] == ["auto", "auto", "auto", "none"]
    cap_note = client.requests[-1][1]["messages"][-1]["content"][-1]
    assert cap_note == {"type": "text", "text": "You have used all 3 tool calls. Write your final answer now."}
    assert result.text == "best guess"


def test_cap_message_can_be_customized():
    """cap_message is formatted with the cap and placed after the last tool result."""
    client = ScriptedClient([resp(add(1, 1, "a")), resp(text("ok"))])
    run(client, max_tool_calls=1, cap_message="Budget of {cap} spent; answer.")
    assert client.requests[1][1]["messages"][-1]["content"][-1]["text"] == "Budget of 1 spent; answer."


def test_calls_beyond_the_cap_are_not_run():
    """Extra tool calls in the same reply are not executed; each still gets an error result."""
    calls = [add(i, i, f"p{i}") for i in range(5)]
    calc = Calculator()
    client = ScriptedClient([resp(*calls), resp(text("ok"))])
    result = run(client, calc, max_tool_calls=3)

    assert len(calc.calls) == 3 and len(result.tool_calls) == 3
    results = tool_results(client.requests[1][1])
    assert [r["tool_use_id"] for r in results] == [f"p{i}" for i in range(5)]
    assert [r.get("is_error", False) for r in results] == [False, False, False, True, True]
    assert results[-1]["content"] == "Not run: the limit of 3 tool calls is reached."
    assert client.requests[1][1]["tool_choice"] == {"type": "none"}


def test_check_can_reject_text_with_a_correction():
    """A check that returns text sends that text back; None accepts the answer."""
    seen = []

    def check(answer, calls):
        seen.append((answer, len(calls)))
        return None if answer == "9" else "Show only the number."

    client = ScriptedClient([resp(add(2, 3, "t1")), resp(text("It is nine")), resp(text("9"))])
    result = run(client, check=check)

    assert result.text == "9"
    assert seen == [("It is nine", 1), ("9", 1)]
    correction = client.requests[2][1]["messages"][-1]
    assert correction == {"role": "user", "content": "Show only the number."}


def test_exceptions_from_check_propagate():
    """The loop does not catch exceptions from check. The caller sees them."""
    class Stop(Exception):
        pass

    def check(answer, calls):
        raise Stop()

    client = ScriptedClient([resp(text("x"))])
    with pytest.raises(Stop):
        run(client, check=check)


def test_gives_up_after_max_requests():
    """If every text answer is rejected, the loop stops after max_requests."""
    client = ScriptedClient([resp(text("no"))] * 3)
    with pytest.raises(AgentDidNotFinish):
        run(client, check=lambda answer, calls: "again", max_requests=3)
    assert len(client.requests) == 3


def test_refusal_and_max_tokens_raise():
    """refusal and max_tokens are failures, even when the reply also contains a tool call."""
    with pytest.raises(AgentRefused):
        run(ScriptedClient([resp(text(""), stop_reason="refusal")]))
    with pytest.raises(AgentOutOfTokens):
        run(ScriptedClient([resp(add(1, 2, "t"), stop_reason="max_tokens")]))


@pytest.mark.parametrize("stop_reason", ["model_context_window_exceeded", "something_new", None])
def test_unexpected_stop_reason_is_never_taken_as_the_answer(stop_reason):
    """A cut-off reply is not treated as the final answer, whatever the unknown reason is."""
    response = resp(text("The answer is 9 but I was cut o"))
    response.stop_reason = stop_reason
    with pytest.raises(AgentStoppedEarly) as caught:
        run(ScriptedClient([response]))
    assert caught.value.stop_reason == stop_reason


def test_pause_turn_is_resumed_by_sending_the_reply_back():
    """pause_turn appends the assistant turn and asks again, without running tools."""
    paused = resp(text("Working on it"), stop_reason="pause_turn")
    client = ScriptedClient([paused, resp(text("9"))])
    result = run(client)
    assert result.text == "9"
    resumed = client.requests[1][1]["messages"]
    assert resumed[-1] == {"role": "assistant", "content": paused.content}


def test_stop_sequence_counts_as_finished():
    """stop_sequence is a finished answer, the same as end_turn."""
    assert run(ScriptedClient([resp(text("9"), stop_reason="stop_sequence")])).text == "9"


def test_tool_from_a_max_tokens_turn_is_never_run():
    """A tool call inside a max_tokens reply is discarded with the rest of that turn."""
    calc = Calculator()
    with pytest.raises(AgentOutOfTokens):
        run(ScriptedClient([resp(add(1, 2, "t"), stop_reason="max_tokens")]), calc)
    assert calc.calls == []


def test_callbacks_report_requests_and_tool_calls_in_order():
    """on_request fires before each model call; on_tool_call fires just before the tool runs."""
    events = []
    client = ScriptedClient([resp(add(2, 3, "t1")), resp(text("5"))])
    run(
        client,
        on_request=lambda: events.append("request"),
        on_tool_call=lambda name, tool_input: events.append((name, tool_input)),
    )
    assert events == ["request", ("add", {"a": 2, "b": 3}), "request"]


def test_agent_module_imports_nothing_from_the_debate_app():
    """The loop stays generic: its imports are only the standard library."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(agent))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "dataclasses", "typing"}
