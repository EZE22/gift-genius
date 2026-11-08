"""Who goes when, plus the app's rules.

The flow (a routing workflow whose specialists are autonomous agents):
  1. route(): one fast LLM call returns one label.
  2. pick_agent(): code maps the label to a specialist; unknown labels get GENERAL.
  3. The specialist runs as an autonomous agent with the catalog tools (cap: 6 calls).
  4. check_shortlist(): code validates the reply. On failure the agent runs once
     more with the specific problems. If that fails too, the gifts that passed
     are shown with the reasons the others were removed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from .agent import AgentError, run_agent
from .agents import FOODIE, GENERAL, MAX_TOOL_CALLS, OUTDOORS, TECH, Specialist, first_message
from .router import LABELS, route
from .tools import run_tool
from .validation import Gift, RemovedGift, check_shortlist

# Event kinds passed to on_event(kind, data)
ROUTED = "routed"  # {"label", "agent", "fallback"}
SEARCHING = "searching"  # {"attempt", "query", "max_price", "matches"}
CHECKING = "checking"  # {"attempt", "item_id", "found", "name"}
VALIDATED = "validated"  # {"attempt", "ok", "problems", "will_retry"}
SHORTLIST = "shortlist"  # the result, as shortlist_data()

MAX_ATTEMPTS = 2  # the first run plus one retry
MAX_DESCRIPTION_LENGTH = 1000
MAX_BUDGET = 10_000

AGENTS: dict[str, Specialist] = {"tech": TECH, "outdoors": OUTDOORS, "foodie": FOODIE}
assert set(AGENTS) == set(LABELS)


class GiftError(Exception):
    """The search can't go on; the message is safe to show the user."""


@dataclass
class GiftResult:
    label: str
    agent: str
    gifts: list[Gift]
    removed: list[RemovedGift] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # empty when the shortlist passed every check
    attempts: int = 1

    @property
    def complete(self) -> bool:
        return not self.problems


OnEvent = Callable[[str, dict], None]


def pick_agent(label: str) -> Specialist:
    """Code, not the model, chooses the agent. Anything unknown falls back to General."""
    return AGENTS.get(label, GENERAL)


def check_request(description: str, budget) -> tuple[str, float]:
    description = description.strip() if isinstance(description, str) else ""
    if not description:
        raise GiftError("Describe the person you're buying for.")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise GiftError(f"Keep the description under {MAX_DESCRIPTION_LENGTH} characters.")
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not (1 <= budget <= MAX_BUDGET):
        raise GiftError(f"Enter a budget between $1 and ${MAX_BUDGET:,}.")
    return description, round(float(budget), 2)


def _tool_runner(attempt: int, emit: OnEvent):
    """Run a tool, then report it to the activity feed."""

    def run(name: str, tool_input: dict) -> tuple[str, bool]:
        content, is_error = run_tool(name, tool_input)
        if name == "search_catalog":
            matches = 0
            if not is_error and content.startswith("{"):
                matches = len(json.loads(content).get("results", []))
            emit(SEARCHING, {
                "attempt": attempt,
                "query": str(tool_input.get("query", ""))[:200],
                "max_price": tool_input.get("max_price"),
                "matches": matches,
            })
        elif name == "get_item":
            found = not is_error
            emit(CHECKING, {
                "attempt": attempt,
                "item_id": str(tool_input.get("item_id", ""))[:60],
                "found": found,
                "name": json.loads(content)["name"] if found else None,
            })
        return content, is_error

    return run


def shortlist_data(result: GiftResult) -> dict:
    return {
        "label": result.label,
        "agent": result.agent,
        "attempts": result.attempts,
        "gifts": [
            {"item_id": g.item_id, "name": g.name, "price": g.price, "link": g.link, "reason": g.reason}
            for g in result.gifts
        ],
        "removed": [{"item_id": r.item_id, "name": r.name, "reasons": list(r.reasons)} for r in result.removed],
        "problems": list(result.problems),
    }


def find_gifts(settings, description: str, budget: float, on_event: Optional[OnEvent] = None) -> GiftResult:
    """Run the whole flow and return the checked shortlist."""
    description, budget = check_request(description, budget)
    emit: OnEvent = on_event or (lambda kind, data: None)

    label = route(settings, description)
    agent = pick_agent(label)
    emit(ROUTED, {"label": label or "(none)", "agent": agent.name, "fallback": agent is GENERAL})

    problems: list[str] | None = None
    check = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            reply = run_agent(
                settings.client,
                system=agent.system,
                first_message=first_message(description, budget, problems),
                tools=agent.tool_schemas,
                run_tool=_tool_runner(attempt, emit),
                max_tool_calls=MAX_TOOL_CALLS,
                model=settings.model,
                server_fallbacks=settings.server_fallbacks,
            )
        except AgentError as error:
            raise GiftError(f"The {agent.name} agent couldn't finish ({type(error).__name__}).") from error
        check = check_shortlist(reply.text, budget)
        will_retry = not check.ok and attempt < MAX_ATTEMPTS
        emit(VALIDATED, {"attempt": attempt, "ok": check.ok, "problems": check.problems, "will_retry": will_retry})
        if check.ok:
            break
        problems = check.problems

    result = GiftResult(label, agent.name, check.passed, check.removed, check.problems, attempt)
    emit(SHORTLIST, shortlist_data(result))
    return result
