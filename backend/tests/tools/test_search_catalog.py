"""Keyword search: stems, stopwords, a price ceiling, and at most eight hits."""

import json

from gift_genius.tools import run_tool, search_catalog


def results(query, max_price):
    """Run a search and return the item list. A no-match message becomes an empty list."""
    content, is_error = search_catalog.run({"query": query, "max_price": max_price})
    assert not is_error
    return json.loads(content)["results"] if content.startswith("{") else []


def test_finds_matching_items_under_the_price():
    """More overlapping words rank higher, and every hit is at or under max_price."""
    found = results("coffee grinder", 200)
    assert found[0]["item_id"] == "food-002"  # Burr Coffee Grinder matches both words
    assert all(r["price"] <= 200 for r in found)
    assert {"item_id", "name", "category", "price", "description", "link"} <= set(found[0])


def test_max_price_filters_out_expensive_items():
    """An item over max_price is absent even when its name matches the query."""
    assert all(r["price"] <= 40 for r in results("camping", 40))
    assert "out-003" not in [r["item_id"] for r in results("tent", 100)]  # $228.99


def test_plurals_and_stopwords():
    """'bags for kayaks' still finds the kayak bag: 'for' is ignored and the plural is stemmed."""
    assert results("bags for kayaks", 50)[0]["item_id"] == "out-014"


def test_at_most_eight_results():
    """A broad query that matches many items still returns at most MAX_RESULTS."""
    assert len(results("cooking baking coffee tea wine", 1000)) <= 8


def test_no_matches_is_a_helpful_message_not_an_error():
    """Zero hits is a sentence for the model, with is_error False, so the call still counts as run."""
    content, is_error = search_catalog.run({"query": "submarine", "max_price": 50})
    assert not is_error and "No items match" in content


def test_bad_input_is_an_error():
    """An empty query, a non-positive price, a bool, or a missing price is an error."""
    assert search_catalog.run({"query": "", "max_price": 50})[1]
    assert search_catalog.run({"query": "tea", "max_price": 0})[1]
    assert search_catalog.run({"query": "tea", "max_price": True})[1]
    assert search_catalog.run({"query": "tea"})[1]


def test_unknown_tool():
    """run_tool rejects a name that is not search_catalog or get_item."""
    assert run_tool("buy_it", {}) == ("Unknown tool 'buy_it'.", True)


def test_word_forms_match():
    """'hiking' matches a description that says 'hikes', because both stem to the same root."""
    assert {r["item_id"] for r in results("hiking", 50)} >= {"out-007"}  # "on hikes"
    assert results("baking bread", 200)
