"""Terminal formatting: budgets, dollar amounts, and one line per progress event."""

import pytest

from gift_genius_cli.ui import format_event, money, parse_budget


@pytest.mark.parametrize("text,value", [("50", 50.0), ("$1,200.50", 1200.5), (" 7 ", 7.0), ("abc", None),
                                        ("", None), ("nan", None), ("inf", None)])
def test_parse_budget(text, value):
    """Dollar signs and commas are allowed. Words, blank text, nan and inf are not."""
    assert parse_budget(text) == value


def test_money():
    """A number prints as dollars and cents. None prints as a question mark."""
    assert money(28.99) == "$28.99" and money(None) == "?"


def test_failed_check_lists_problems():
    """A failed validation lists each problem and says the agent will try once more."""
    line = format_event("validated", {"attempt": 1, "ok": False, "problems": ["A: bad link."], "will_retry": True})
    assert "- A: bad link." in line and "try once more" in line


def test_retry_lines_are_marked():
    """Tool-call lines from attempt 2 are prefixed so a retry is visible in the transcript."""
    line = format_event("checking", {"attempt": 2, "item_id": "x-1", "found": False, "name": None})
    assert "(retry)" in line and "not in the catalog" in line
