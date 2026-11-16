"""A scripted stand-in for the Claude client. Uses only the back end's public API."""

import json
from types import SimpleNamespace

from gift_genius import Settings


def text(t):
    """A text block in a fake model reply."""
    return SimpleNamespace(type="text", text=t)


def tool(name, tool_input, id="t1"):
    """A tool_use block in a fake model reply."""
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=id)


def resp(*blocks):
    """One fake Messages API response. Tool blocks imply stop_reason tool_use."""
    stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


class ScriptedClient:
    """Plays scripted replies in order. Each messages.create consumes the next one."""

    def __init__(self, script):
        self.script = list(script)
        self.messages = SimpleNamespace(create=lambda **kw: self.script.pop(0))


# Three real outdoors items, all under $50, copied in the shape the shortlist uses.
GIFTS = [
    {"item_id": "out-007", "name": "Insulated Water Bottle", "price": 28.99,
     "link": "https://gifts.example.com/item/out-007", "reason": "Keeps water cold on long hikes."},
    {"item_id": "out-006", "name": "Headlamp Rechargeable", "price": 31.99,
     "link": "https://gifts.example.com/item/out-006", "reason": "Lights the trail at dusk."},
    {"item_id": "out-012", "name": "Bike Multi-Tool", "price": 25.99,
     "link": "https://gifts.example.com/item/out-012", "reason": "Fixes a bike anywhere."},
]


def reply(gifts):
    """A finished specialist turn whose text is the shortlist JSON."""
    return resp(text(json.dumps({"gifts": gifts})))


def factory(script):
    """A settings_factory the CLI can call instead of reading .env.

    claude_features is passed by name and set to True because this fake plays a
    Claude client. Settings gained that field when Ollama support was added, and
    a missing value here made every CLI search fail with exit code 1.
    """
    return lambda: Settings(ScriptedClient(script), "main", "router", False, claude_features=True)


def answers(*values):
    """A stand-in for input() that returns these lines, one prompt at a time."""
    it = iter(values)
    return lambda prompt="": next(it)
