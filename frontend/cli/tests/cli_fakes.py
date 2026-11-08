"""A scripted stand-in for the Claude client. Uses only the back end's public API."""

import json
from types import SimpleNamespace

from gift_genius import Settings


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(name, tool_input, id="t1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=id)


def resp(*blocks):
    stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


class ScriptedClient:
    def __init__(self, script):
        self.script = list(script)
        self.messages = SimpleNamespace(create=lambda **kw: self.script.pop(0))


GIFTS = [
    {"item_id": "out-007", "name": "Insulated Water Bottle", "price": 28.99,
     "link": "https://gifts.example.com/item/out-007", "reason": "Keeps water cold on long hikes."},
    {"item_id": "out-006", "name": "Headlamp Rechargeable", "price": 31.99,
     "link": "https://gifts.example.com/item/out-006", "reason": "Lights the trail at dusk."},
    {"item_id": "out-012", "name": "Bike Multi-Tool", "price": 25.99,
     "link": "https://gifts.example.com/item/out-012", "reason": "Fixes a bike anywhere."},
]


def reply(gifts):
    return resp(text(json.dumps({"gifts": gifts})))


def factory(script):
    return lambda: Settings(ScriptedClient(script), "main", "router", False)


def answers(*values):
    it = iter(values)
    return lambda prompt="": next(it)
