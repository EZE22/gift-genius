"""The gift-genius command: ask for a description and a budget, then show three checked gifts.

  gift-genius
  gift-genius --budget 50 "My sister loves trail running and good coffee"
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, TextIO

from gift_genius import (
    MAX_BUDGET,
    MAX_DESCRIPTION_LENGTH,
    describe_error,
    find_gifts,
    load_env,
    make_client,
)

from .ui import format_event, format_result, parse_budget


def ask_description(ask: Callable[[str], str], out: TextIO) -> str:
    """Prompt until the text is non-empty and within the length limit."""
    while True:
        text = ask("Describe the person you're buying for: ").strip()
        if text and len(text) <= MAX_DESCRIPTION_LENGTH:
            return text
        print(f"  Enter a description of up to {MAX_DESCRIPTION_LENGTH} characters.", file=out)


def ask_budget(ask: Callable[[str], str], out: TextIO) -> float:
    """Prompt until the line parses as a budget inside the allowed range."""
    while True:
        value = parse_budget(ask("Budget per gift, in dollars: "))
        if value is not None and 1 <= value <= MAX_BUDGET:
            return value
        print(f"  Enter a number between 1 and {MAX_BUDGET:,}, like 50.", file=out)


def main(argv=None, ask: Callable[[str], str] = input, out: TextIO = sys.stdout, settings_factory=make_client) -> int:
    """Run one search. Returns a process exit code: 0 ok, 1 failed, 130 cancelled.

    Tests pass argv, a fake ask, a StringIO, and a settings_factory so this
    never reads the real .env or calls a model.
    """
    parser = argparse.ArgumentParser(prog="gift-genius", description="Find three gift ideas for someone, within a budget.")
    parser.add_argument("description", nargs="?", help="who the gift is for")
    parser.add_argument("--budget", help="budget per gift in dollars, e.g. 50")
    args = parser.parse_args(argv)

    print("Gift Genius\n", file=out)
    try:
        # Missing or blank arguments fall through to a prompt. A budget that
        # was given but does not parse is reported, then the prompt takes over.
        description = args.description.strip() if args.description and args.description.strip() else ask_description(ask, out)
        budget = parse_budget(args.budget) if args.budget else None
        if budget is None or not 1 <= budget <= MAX_BUDGET:
            if args.budget:
                print(f"  {args.budget!r} isn't a budget between 1 and {MAX_BUDGET:,}.", file=out)
            budget = ask_budget(ask, out)
    except (EOFError, KeyboardInterrupt):
        print("\nNo search run.", file=out)
        return 130

    print("\nFinding gifts...", file=out)

    def on_event(kind: str, data: dict) -> None:
        # flush so a long model call still shows each line as it happens.
        line = format_event(kind, data)
        if line:
            print(line, file=out, flush=True)

    try:
        load_env()
        result = find_gifts(settings_factory(), description, budget, on_event)
    except KeyboardInterrupt:
        print("\nStopped.", file=out)
        return 130
    except Exception as error:  # shown as a friendly message, never a traceback with secrets
        print(f"\n{describe_error(error)}", file=out)
        return 1
    print(format_result(result), file=out)
    return 0


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
