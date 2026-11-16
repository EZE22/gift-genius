"""The router: one call to a fast model that returns exactly one label.

It only labels the request. Code (orchestrator.pick_agent) maps the label to
an agent, so a label outside LABELS can never pick anything but the fallback.
"""

from __future__ import annotations

import re

LABELS = ("tech", "outdoors", "foodie")

# Thinking can't be turned off on current models and counts toward max_tokens,
# so leave room for a short think at low effort plus the one-word answer.
ROUTER_MAX_TOKENS = 2000
ROUTER_EFFORT = "low"

SYSTEM = (
    "You sort gift requests for a gift shop. Read the description of the person "
    "who will receive the gift and pick the one category that fits them best:\n"
    "- tech: gadgets, computers, gaming, smart home, audio, photography\n"
    "- outdoors: hiking, camping, cycling, running, gardening, travel, sport\n"
    "- foodie: cooking, baking, coffee, tea, wine, specialty food\n"
    "Reply with only the label: tech, outdoors or foodie. No other words."
)


def normalize(text: str) -> str:
    """The first word of the reply, lowercased, without punctuation ("Tech." -> "tech")."""
    match = re.search(r"[a-z]+", text.lower())
    return match.group(0) if match else ""


def route(settings, description: str) -> str:
    """Return the router's label. It may be outside LABELS; the caller falls back.

    This is a single request with no tools. The description is wrapped in a tag
    so the model treats it as the shopper's words, not as new instructions.
    """
    # The request every model accepts.
    params = dict(
        model=settings.router_model,
        max_tokens=ROUTER_MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"<description>\n{description}\n</description>"}],
    )
    if settings.claude_features:
        # The effort setting is Claude-only. Ollama does not understand it, so it is
        # sent only when the model source is Claude or Foundry.
        params["output_config"] = {"effort": ROUTER_EFFORT}
    response = settings.client.messages.create(**params)
    if response.stop_reason not in ("end_turn", "stop_sequence"):
        return ""  # refused or cut off: no label, so the fallback agent runs
    # Thinking blocks are ignored. Only the text the model wrote is a label.
    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    return normalize(text)
