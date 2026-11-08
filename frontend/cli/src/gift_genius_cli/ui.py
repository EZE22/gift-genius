"""Turn back end events and results into terminal text. Pure functions, easy to test."""

from __future__ import annotations

from gift_genius import CHECKING, ROUTED, SEARCHING, SHORTLIST, VALIDATED


def money(value) -> str:
    """Format a dollar amount. A value that is not a number becomes '?'."""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "?"


def parse_budget(text: str) -> float | None:
    """'50', '$50', '1,200.50' -> a number; anything else -> None."""
    cleaned = text.strip().replace("$", "").replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value == value and value not in (float("inf"), float("-inf")) else None


def format_event(kind: str, data: dict) -> str | None:
    """One activity-feed line, or None for events shown another way.

    The shortlist event is skipped here because format_result prints the cards.
    Any other unknown kind is also skipped, so a newer server event cannot
    crash an older CLI.
    """
    retry = "  (retry) " if data.get("attempt", 1) > 1 else "  "
    if kind == ROUTED:
        if data["fallback"]:
            return f"  Router said {data['label']!r}, which isn't a category, so the General agent takes it."
        return f"  Router: {data['label']}. The {data['agent']} agent is on it."
    if kind == SEARCHING:
        found = data.get("matches", 0)
        return f"{retry}Searching the catalog for {data['query']!r} up to {money(data['max_price'])}: {found} match{'es' if found != 1 else ''}"
    if kind == CHECKING:
        if data.get("found"):
            return f"{retry}Checking {data['item_id']}: {data['name']}"
        return f"{retry}Checking {data['item_id']}: not in the catalog"
    if kind == VALIDATED:
        if data["ok"]:
            return f"{retry}Checks passed: three gifts, all in the catalog, under budget, with catalog links."
        lines = [f"{retry}Checks failed:"] + [f"      - {p}" for p in data["problems"]]
        if data.get("will_retry"):
            lines.append("    Asking the agent to try once more with these problems.")
        return "\n".join(lines)
    if kind == SHORTLIST:
        return None
    return None


def format_result(result) -> str:
    """The gift cards, plus any removed gifts and why."""
    lines = [""]
    if result.gifts:
        heading = "Three gift ideas" if result.complete else f"{len(result.gifts)} gift idea{'s' if len(result.gifts) != 1 else ''} passed the checks"
        lines.append(f"{heading} (from the {result.agent} agent):")
        for n, gift in enumerate(result.gifts, 1):
            lines += ["", f"{n}. {gift.name}  {money(gift.price)}", f"   {gift.reason}", f"   {gift.link}"]
    else:
        lines.append("No gift ideas passed the checks.")
    if not result.complete:
        # Each removed gift already explains itself. `other` is what is left:
        # problems about the shortlist as a whole, such as the wrong count.
        lines += ["", "Some suggestions were removed after two tries:"]
        for removed in result.removed:
            lines.append(f"  - {removed.name}: {'; '.join(removed.reasons)}")
        other = [p for p in result.problems if not any(p.startswith(f"{r.name} (") for r in result.removed)]
        for problem in other:
            lines.append(f"  - {problem}")
    return "\n".join(lines)
