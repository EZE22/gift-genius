"""Code checks on the agent's shortlist: count, catalog ids, budget, links."""

import pytest

from gift_genius.validation import check_shortlist, parse_shortlist

from fakes import GOOD_OUTDOORS, gift, shortlist

BUDGET = 50


def test_three_good_gifts_pass_and_come_from_the_catalog():
    reply = shortlist(gift("out-007", name="Shiny Bottle!!"), gift("out-006"), gift("out-012"))
    # A wrong name isn't a failure: the user sees the catalog's name.
    check = check_shortlist(reply, BUDGET)
    assert check.ok and check.problems == [] and check.removed == []
    assert [g.item_id for g in check.passed] == ["out-007", "out-006", "out-012"]
    assert check.passed[0].name == "Insulated Water Bottle"
    assert check.passed[0].link == "https://gifts.example.com/item/out-007"


def test_over_budget_price_is_removed():
    reply = shortlist(gift("out-007"), gift("out-006"), gift("tech-002"))  # headphones $188.99
    check = check_shortlist(reply, BUDGET)
    assert not check.ok
    assert [g.item_id for g in check.passed] == ["out-007", "out-006"]
    [removed] = check.removed
    assert removed.item_id == "tech-002"
    assert "price $188.99 is over the $50.00 budget" in removed.reasons
    assert any("over the $50.00 budget" in p for p in check.problems)


def test_understated_price_for_an_over_budget_item_is_caught():
    reply = shortlist(gift("out-007"), gift("out-006"), gift("tech-002", price=45))
    check = check_shortlist(reply, BUDGET)
    reasons = check.removed[0].reasons
    assert "price $45.00 doesn't match the catalog price $188.99" in reasons
    assert "catalog price $188.99 is over the $50.00 budget" in reasons


def test_price_exactly_at_budget_passes():
    reply = shortlist(*(gift(i) for i in GOOD_OUTDOORS))
    assert check_shortlist(reply, 31.99).ok


def test_unknown_item_id_is_removed():
    reply = shortlist(gift("out-007"), gift("out-006"),
                      {"item_id": "out-999", "name": "Magic Tent", "price": 20, "link": "https://x.test", "reason": "Fun."})
    check = check_shortlist(reply, BUDGET)
    assert not check.ok
    [removed] = check.removed
    assert removed.name == "Magic Tent"
    assert removed.reasons == ("item_id 'out-999' is not in the catalog",)


def test_missing_item_id_is_removed():
    reply = shortlist(gift("out-007"), gift("out-006"), {"name": "Mystery", "price": 10, "reason": "Fun."})
    assert check_shortlist(reply, BUDGET).removed[0].reasons == ("item_id '(missing)' is not in the catalog",)


def test_wrong_link_is_removed():
    reply = shortlist(gift("out-007"), gift("out-006"), gift("out-012", link="https://evil.example/buy"))
    check = check_shortlist(reply, BUDGET)
    [removed] = check.removed
    assert removed.item_id == "out-012"
    assert removed.reasons == (
        "link 'https://evil.example/buy' doesn't match the catalog link https://gifts.example.com/item/out-012",
    )


@pytest.mark.parametrize("count", [2, 4])
def test_exactly_three_gifts_required(count):
    ids = ["out-007", "out-006", "out-012", "out-014"][:count]
    check = check_shortlist(shortlist(*(gift(i) for i in ids)), BUDGET)
    assert not check.ok
    assert f"Expected exactly 3 gifts but got {count}." in check.problems
    assert len(check.passed) == min(count, 3)
    if count == 4:
        assert check.removed[0].reasons == ("is beyond the first three gifts",)


def test_duplicate_gift_is_removed():
    check = check_shortlist(shortlist(gift("out-007"), gift("out-007"), gift("out-012")), BUDGET)
    assert check.removed[0].reasons == ("is listed more than once",)
    assert len(check.passed) == 2


def test_gift_without_reason_is_removed():
    check = check_shortlist(shortlist(gift("out-007"), gift("out-006"), gift("out-012", reason="  ")), BUDGET)
    assert check.removed[0].reasons == ("has no reason",)


def test_one_gift_can_fail_several_checks():
    check = check_shortlist(
        shortlist(gift("out-007"), gift("out-006"), gift("food-010", link="https://x.test")), BUDGET
    )
    assert len(check.removed[0].reasons) == 2


def test_reply_that_is_not_json_fails_everything():
    check = check_shortlist("Here are some ideas: a tent, a stove.", BUDGET)
    assert not check.ok and check.passed == [] and len(check.problems) == 1


def test_json_inside_a_code_fence_or_sentence_is_read():
    body = shortlist(*(gift(i) for i in GOOD_OUTDOORS))
    assert len(parse_shortlist(f"```json\n{body}\n```")) == 3
    assert len(parse_shortlist(f"Here you go: {body} Enjoy!")) == 3


def test_price_given_as_text_is_read():
    check = check_shortlist(shortlist(gift("out-007", price="$28.99"), gift("out-006"), gift("out-012")), BUDGET)
    assert check.ok


def test_long_reason_is_cut():
    check = check_shortlist(shortlist(gift("out-007", reason="x" * 1000), gift("out-006"), gift("out-012")), BUDGET)
    assert len(check.passed[0].reason) == 300
