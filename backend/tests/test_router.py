"""The router: one call, one label."""

import pytest

from gift_genius.router import LABELS, ROUTER_EFFORT, normalize, route

from fakes import resp, settings, text


def test_one_call_to_the_router_model_returns_the_label():
    """One request, to the router model, with no tools, and the description inside a tag."""
    s = settings([resp(text("outdoors"))])
    assert route(s, "Loves hiking") == "outdoors"
    [(api, request)] = s.client.requests
    assert request["model"] == "router-model"
    assert request["output_config"] == {"effort": ROUTER_EFFORT}
    assert "tools" not in request
    assert "<description>\nLoves hiking\n</description>" in request["messages"][0]["content"]


def test_without_claude_features_the_router_sends_no_effort_setting():
    """Ollama does not understand output_config, so with claude_features off the router
    leaves it out. The label still comes back."""
    s = settings([resp(text("outdoors"))], claude_features=False)
    assert route(s, "Loves hiking") == "outdoors"
    [(api, request)] = s.client.requests
    assert "output_config" not in request


@pytest.mark.parametrize("reply,label", [("Tech.", "tech"), ("  FOODIE\n", "foodie"), ("outdoors - hikes", "outdoors"),
                                         ("books", "books"), ("", "")])
def test_normalize(reply, label):
    """The label is the first word, lowercased, with punctuation stripped."""
    assert normalize(reply) == label


def test_refusal_gives_no_label():
    """A refusal is an empty label, which the orchestrator treats as the General fallback."""
    s = settings([resp(stop_reason="refusal")])
    assert route(s, "x") == ""


def test_labels_are_the_three_categories():
    """The only labels the router is asked to return. pick_agent's map must match this tuple."""
    assert LABELS == ("tech", "outdoors", "foodie")
