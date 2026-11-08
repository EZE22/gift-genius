"""The CLI journey with the model mocked."""

import io

from gift_genius import ConfigError
from gift_genius_cli.__main__ import main

from cli_fakes import GIFTS, answers, factory, reply, resp, text, tool


def run(argv, script, ask=None):
    out = io.StringIO()
    code = main(argv, ask=ask or answers(), out=out, settings_factory=factory(script))
    return code, out.getvalue()


def test_full_search_from_arguments():
    script = [resp(text("outdoors")), resp(tool("search_catalog", {"query": "hiking", "max_price": 50})), reply(GIFTS)]
    code, out = run(["--budget", "50", "Loves hiking"], script)
    assert code == 0
    assert "Router: outdoors. The Outdoors agent is on it." in out
    assert "Searching the catalog for 'hiking' up to $50.00" in out
    assert "Checks passed" in out
    assert "Three gift ideas (from the Outdoors agent):" in out
    assert "1. Insulated Water Bottle  $28.99" in out
    assert "https://gifts.example.com/item/out-012" in out


def test_asks_for_missing_values_and_repeats_bad_ones():
    script = [resp(text("outdoors")), reply(GIFTS)]
    code, out = run([], script, ask=answers("  ", "Loves hiking", "lots", "0", "$50"))
    assert code == 0
    assert "Enter a description" in out
    assert out.count("Enter a number between 1 and 10,000") == 2


def test_retry_then_partial_result_explains_removals():
    over = dict(GIFTS[2], item_id="tech-002", name="Noise-Cancelling Headphones", price=188.99,
                link="https://gifts.example.com/item/tech-002")
    script = [resp(text("outdoors")), reply(GIFTS[:2] + [over]), reply(GIFTS[:2] + [over])]
    code, out = run(["--budget", "50", "Loves hiking"], script)
    assert code == 0
    assert "Asking the agent to try once more" in out
    assert "2 gift ideas passed the checks" in out
    assert "Noise-Cancelling Headphones: price $188.99 is over the $50.00 budget" in out


def test_unknown_label_uses_general():
    code, out = run(["--budget", "50", "Someone"], [resp(text("books")), reply(GIFTS)])
    assert "isn't a category, so the General agent takes it" in out


def test_errors_are_friendly():
    def broken():
        raise ConfigError("missing")

    out = io.StringIO()
    code = main(["--budget", "50", "x"], ask=answers(), out=out, settings_factory=broken)
    assert code == 1 and "isn't set up to call Claude" in out.getvalue() and "Traceback" not in out.getvalue()


def test_ctrl_d_at_a_prompt_exits_cleanly():
    def eof(prompt=""):
        raise EOFError

    out = io.StringIO()
    assert main([], ask=eof, out=out, settings_factory=factory([])) == 130
    assert "No search run." in out.getvalue()
