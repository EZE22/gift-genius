"""The HTTP API streams the flow as Server-Sent Events. The model is mocked."""

import asyncio
import json
import threading

import anthropic
import httpx
from fastapi.testclient import TestClient

from gift_genius.api.app import BUSY_MESSAGE, create_app, describe_error, search_events
from gift_genius.client import ConfigError
from gift_genius.orchestrator import GiftError

from fakes import get, good_reply, resp, search, settings, text

SECRET = "sk-test-SECRET-123"


def parse(body: str):
    """Split an SSE body into (event name, data) pairs. Keep-alive comments are skipped."""
    events = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        if lines[0].startswith(":"):
            continue
        name = lines[0].removeprefix("event: ")
        events.append((name, json.loads(lines[1].removeprefix("data: "))))
    return events


def post(app, payload):
    """POST one search and return the response. TestClient reads the stream to the end."""
    with TestClient(app) as client:
        return client.post("/api/gift-searches", json=payload)


def test_streams_every_event_kind_in_order():
    """A successful search streams the six event kinds, ending in done, with three gifts."""
    script = [resp(text("outdoors")), resp(search("hiking", 50)), resp(get("out-007")), good_reply()]
    app = create_app(lambda: settings(script))
    response = post(app, {"description": "Loves hiking", "budget": 50})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    names = [n for n, _ in parse(response.text)]
    assert names == ["routed", "searching", "checking", "validated", "shortlist", "done"]
    shortlist = parse(response.text)[4][1]
    assert len(shortlist["gifts"]) == 3 and shortlist["removed"] == [] and shortlist["problems"] == []


def test_bad_requests_are_rejected():
    """Blank text, a bad budget, an oversized description, or a missing field is HTTP 422."""
    app = create_app(lambda: settings([]))
    for payload in ({"description": "  ", "budget": 50}, {"description": "x", "budget": 0},
                    {"description": "x" * 1001, "budget": 50}, {"description": "x"}, {"budget": 50}):
        assert post(app, payload).status_code == 422


def test_errors_become_an_error_event_without_secrets():
    """A failure while building the client becomes one error event with the safe message."""
    def factory():
        raise ConfigError("no key")

    events = parse(post(create_app(factory), {"description": "x", "budget": 20}).text)
    assert events == [("error", {"message": describe_error(ConfigError())})]


def test_api_errors_never_leak_the_key():
    """An authentication error that mentions the key is rewritten. The key is not in the body."""
    request = httpx.Request("POST", "https://api.test")
    error = anthropic.AuthenticationError(f"bad key {SECRET}", response=httpx.Response(401, request=request), body=None)
    s = settings([error])
    s.client.messages.create = lambda **kw: (_ for _ in ()).throw(error)
    body = post(create_app(lambda: s), {"description": "x", "budget": 20}).text
    assert SECRET not in body
    assert parse(body) == [("error", {"message": "The Claude API key in .env was rejected."})]


def test_gift_error_message_is_shown():
    """GiftError text is shown as written. Any other exception becomes the generic sentence."""
    assert describe_error(GiftError("Describe the person.")) == "Describe the person."
    assert "went wrong" in describe_error(RuntimeError(SECRET))


def test_busy_when_all_slots_are_taken():
    """If every search slot is held, the stream is a single busy error and no search starts."""
    slots = threading.BoundedSemaphore(1)
    slots.acquire()

    async def collect():
        return [c async for c in search_events("x", 20, lambda: settings([]), slots=slots)]

    [chunk] = asyncio.run(collect())
    assert BUSY_MESSAGE in chunk


def test_health():
    """GET /api/health is a cheap check that the process is up. It does not call the model."""
    with TestClient(create_app(lambda: settings([]))) as client:
        assert client.get("/api/health").json() == {"ok": True}
