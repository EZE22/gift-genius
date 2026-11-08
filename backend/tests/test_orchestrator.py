"""The whole flow with the model mocked: route, pick, run, check, retry once."""

import pytest

from gift_genius.agents import FOODIE, GENERAL, OUTDOORS, TECH
from gift_genius.orchestrator import GiftError, find_gifts, pick_agent

from fakes import GOOD_OUTDOORS, get, gift, good_reply, resp, search, settings, shortlist, text, tool_results


def run(script, description="Loves hiking and camping", budget=50):
    events = []
    s = settings(script)
    result = find_gifts(s, description, budget, lambda kind, data: events.append((kind, data)))
    return result, events, s.client.requests


def kinds(events):
    return [k for k, _ in events]


@pytest.mark.parametrize("label,agent", [("tech", TECH), ("outdoors", OUTDOORS), ("foodie", FOODIE),
                                         ("books", GENERAL), ("", GENERAL), ("Tech", GENERAL)])
def test_code_maps_labels_to_agents_with_a_fallback(label, agent):
    assert pick_agent(label) is agent


def test_happy_path_routes_searches_checks_and_returns_three_gifts():
    result, events, requests = run([
        resp(text("outdoors")),
        resp(search("hiking", 50)),
        resp(get("out-007")),
        good_reply(),
    ])
    assert (result.label, result.agent, result.attempts, result.complete) == ("outdoors", "Outdoors", 1, True)
    assert [g.item_id for g in result.gifts] == list(GOOD_OUTDOORS)
    assert kinds(events) == ["routed", "searching", "checking", "validated", "shortlist"]
    assert events[0][1] == {"label": "outdoors", "agent": "Outdoors", "fallback": False}
    assert events[1][1]["query"] == "hiking" and events[1][1]["matches"] > 0
    assert events[2][1] == {"attempt": 1, "item_id": "out-007", "found": True, "name": "Insulated Water Bottle"}
    assert events[3][1] == {"attempt": 1, "ok": True, "problems": [], "will_retry": False}
    # The router used the router model; the agent used the main model, with the Outdoors prompt.
    assert requests[0][1]["model"] == "router-model"
    assert requests[1][1]["model"] == "main-model"
    assert requests[1][1]["system"] == OUTDOORS.system
    assert "Budget: $50.00" in requests[1][1]["messages"][0]["content"]


def test_unknown_label_falls_back_to_general():
    result, events, requests = run([resp(text("books")), good_reply()])
    assert events[0][1] == {"label": "books", "agent": "General", "fallback": True}
    assert requests[1][1]["system"] == GENERAL.system
    assert result.agent == "General"


def test_agent_is_capped_at_six_tool_calls():
    script = [resp(text("outdoors"))] + [resp(search(f"q{i}", 50, id=f"s{i}")) for i in range(6)] + [good_reply()]
    result, events, requests = run(script)
    assert kinds(events).count("searching") == 6
    assert requests[-1][1]["tool_choice"] == {"type": "none"}  # the 7th request forbids tools
    assert result.complete


def test_failed_check_retries_once_with_the_specific_problems():
    bad = resp(text(shortlist(gift("out-007"), gift("out-006"), gift("tech-002"))))  # $188.99 headphones
    result, events, requests = run([resp(text("outdoors")), bad, good_reply()])
    assert kinds(events) == ["routed", "validated", "validated", "shortlist"]
    first, second = events[1][1], events[2][1]
    assert (first["attempt"], first["ok"], first["will_retry"]) == (1, False, True)
    assert any("over the $50.00 budget" in p for p in first["problems"])
    assert (second["attempt"], second["ok"]) == (2, True)
    retry_message = requests[2][1]["messages"][0]["content"]
    assert "Your previous shortlist failed these checks" in retry_message
    assert "price $188.99 is over the $50.00 budget" in retry_message
    assert result.complete and result.attempts == 2 and result.removed == []


def test_second_failure_shows_the_gifts_that_passed_and_why_others_were_removed():
    bad1 = resp(text(shortlist(gift("out-007"), gift("out-006"), gift("tech-002"))))
    bad2 = resp(text(shortlist(gift("out-007"), gift("out-006"), gift("out-012", link="https://x.test"))))
    result, events, _ = run([resp(text("outdoors")), bad1, bad2])
    assert kinds(events) == ["routed", "validated", "validated", "shortlist"]
    assert events[2][1]["will_retry"] is False
    assert not result.complete and result.attempts == 2
    assert [g.item_id for g in result.gifts] == ["out-007", "out-006"]
    [removed] = result.removed
    assert removed.item_id == "out-012" and "doesn't match the catalog link" in removed.reasons[0]
    shown = events[3][1]
    assert shown["removed"][0]["reasons"] == list(removed.reasons)
    assert shown["problems"] == result.problems


def test_unknown_item_and_retry_use_fresh_tool_budget():
    bad = resp(text(shortlist(gift("out-007"), gift("out-006"),
                              {"item_id": "out-404", "name": "Ghost", "price": 9, "link": "x", "reason": "r"})))
    script = [resp(text("outdoors")), resp(get("out-404")), bad, resp(search("bike", 50)), good_reply()]
    result, events, requests = run(script)
    checking = [d for k, d in events if k == "checking"]
    assert checking == [{"attempt": 1, "item_id": "out-404", "found": False, "name": None}]
    assert tool_results(requests[2][1])[0]["is_error"] is True
    assert [d["attempt"] for k, d in events if k == "searching"] == [2]
    assert result.complete


@pytest.mark.parametrize("description,budget", [("  ", 50), ("x" * 1001, 50), ("ok", 0), ("ok", 0.5),
                                                ("ok", 10_001), ("ok", True), ("ok", "50")])
def test_bad_requests_stop_before_any_model_call(description, budget):
    s = settings([])
    with pytest.raises(GiftError):
        find_gifts(s, description, budget)
    assert s.client.requests == []


def test_agent_that_cannot_finish_is_a_gift_error():
    with pytest.raises(GiftError, match="Outdoors agent couldn't finish"):
        run([resp(text("outdoors")), resp(stop_reason="max_tokens")])
