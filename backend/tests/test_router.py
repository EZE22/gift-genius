"""The router: one call, one label."""

import pytest

from gift_genius.router import LABELS, ROUTER_EFFORT, normalize, route

from fakes import resp, settings, text


def test_one_call_to_the_router_model_returns_the_label():
    s = settings([resp(text("outdoors"))])
    assert route(s, "Loves hiking") == "outdoors"
    [(api, request)] = s.client.requests
    assert request["model"] == "router-model"
    assert request["output_config"] == {"effort": ROUTER_EFFORT}
    assert "tools" not in request
    assert "<description>\nLoves hiking\n</description>" in request["messages"][0]["content"]


@pytest.mark.parametrize("reply,label", [("Tech.", "tech"), ("  FOODIE\n", "foodie"), ("outdoors - hikes", "outdoors"),
                                         ("books", "books"), ("", "")])
def test_normalize(reply, label):
    assert normalize(reply) == label


def test_refusal_gives_no_label():
    s = settings([resp(stop_reason="refusal")])
    assert route(s, "x") == ""


def test_labels_are_the_three_categories():
    assert LABELS == ("tech", "outdoors", "foodie")
