"""Test doubles: a scripted Claude client and helpers. No test calls a real model."""

import copy
import json
from types import SimpleNamespace

from gift_genius.client import Settings
from gift_genius.tools.catalog import load_catalog


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(name, tool_input, id):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=id)


def search(query, max_price=100, id="s1"):
    return tool("search_catalog", {"query": query, "max_price": max_price}, id)


def get(item_id, id="g1"):
    return tool("get_item", {"item_id": item_id}, id)


def resp(*blocks, stop_reason=None):
    """A fake Messages API response. A thinking block leads, as on Opus 5.5."""
    if stop_reason is None:
        stop_reason = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    thinking = SimpleNamespace(type="thinking", thinking="", signature="sig")
    return SimpleNamespace(content=[thinking, *blocks], stop_reason=stop_reason)


class ScriptedClient:
    """Fake Anthropic client. Each create() call takes the next scripted item:
    a response, or a function(request_kwargs) -> response."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.messages = SimpleNamespace(create=lambda **kw: self._next("plain", kw))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: self._next("beta", kw)))

    def _next(self, api, kwargs):
        self.requests.append((api, copy.deepcopy(kwargs)))
        if not self.script:
            raise AssertionError("ScriptedClient ran out of scripted responses")
        item = self.script.pop(0)
        return item(kwargs) if callable(item) else item


def settings(script, model="main-model", router_model="router-model"):
    return Settings(ScriptedClient(script), model, router_model, False)


def tool_results(request):
    content = request["messages"][-1]["content"]
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]


def gift(item_id, **overrides):
    """A shortlist entry copied from the catalog, with optional wrong fields."""
    item = load_catalog()[item_id]
    entry = {"item_id": item.id, "name": item.name, "price": item.price, "link": item.link,
             "reason": f"They would enjoy the {item.name}."}
    entry.update(overrides)
    return entry


def shortlist(*gifts):
    return json.dumps({"gifts": list(gifts)})


GOOD_OUTDOORS = ("out-007", "out-006", "out-012")  # $28.99, $31.99, $25.99


def good_reply():
    return resp(text(shortlist(*(gift(i) for i in GOOD_OUTDOORS))))
