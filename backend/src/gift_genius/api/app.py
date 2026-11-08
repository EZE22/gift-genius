"""HTTP API for Gift Genius: run one gift search and stream its progress as Server-Sent Events.

POST /api/gift-searches with {"description": "...", "budget": 50} returns a text/event-stream:

  routed     {"label", "agent", "fallback"}                     the router's label and the agent code picked
  searching  {"attempt", "query", "max_price", "matches"}       the agent called search_catalog
  checking   {"attempt", "item_id", "found", "name"}            the agent called get_item
  validated  {"attempt", "ok", "problems", "will_retry"}        code checked the agent's shortlist
  shortlist  {"label", "agent", "attempts", "gifts", "removed", "problems"}
  done       {}
  error      {"message"}                                        the search stopped; the message is safe to show

While nothing else happens the stream sends ": keep-alive" every few seconds.
The API key stays in the server's environment: it is in no event, error or response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from ..client import load_env, make_client
from ..errors import GENERIC_MESSAGE, describe_error, log_failure
from ..orchestrator import MAX_BUDGET, MAX_DESCRIPTION_LENGTH, find_gifts

log = logging.getLogger("gift_genius.api")

MAX_CONCURRENT_SEARCHES = 3  # each search is a thread making paid Claude calls
SEARCH_DEADLINE_SECONDS = 6 * 60
HEARTBEAT_SECONDS = 15
KEEP_ALIVE = ": keep-alive\n\n"

BUSY_MESSAGE = "The server is busy with other searches. Try again in a minute."
TIMEOUT_MESSAGE = "The search took too long and was stopped. Try again."


class SearchRequest(BaseModel):
    description: str = Field(max_length=MAX_DESCRIPTION_LENGTH)
    budget: float = Field(ge=1, le=MAX_BUDGET)

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Describe the person you're buying for.")
        return value


class _Cancelled(Exception):
    """The client went away; stop at the next event."""


class _TimedOut(Exception):
    """The search passed its deadline; stop at the next event."""


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def search_events(
    description: str,
    budget: float,
    client_factory: Callable = make_client,
    *,
    slots: Optional[threading.Semaphore] = None,
    deadline_seconds: float = SEARCH_DEADLINE_SECONDS,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Run one search in a worker thread and yield its events as SSE text."""
    if slots is not None and not slots.acquire(blocking=False):
        yield sse("error", {"message": BUSY_MESSAGE})
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    cancelled = threading.Event()
    deadline = time.monotonic() + deadline_seconds

    def push(item) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, item)
        except RuntimeError:  # the event loop closed (server shutdown)
            pass

    def on_event(kind: str, data: dict) -> None:
        if cancelled.is_set():
            raise _Cancelled()
        if time.monotonic() > deadline:
            raise _TimedOut()
        push(sse(kind, data))

    def work() -> None:
        final = None
        try:
            settings = client_factory()
            find_gifts(settings, description, budget, on_event)
            final = sse("done", {})
        except _Cancelled:
            pass
        except _TimedOut:
            log.warning("Search stopped after %s seconds", deadline_seconds)
            final = sse("error", {"message": TIMEOUT_MESSAGE})
        except Exception as error:  # every failure becomes an error event
            log_failure(error)
            final = sse("error", {"message": describe_error(error)})
        finally:
            if final is None and not cancelled.is_set():
                log.error("Search worker ended without a result")
                final = sse("error", {"message": GENERIC_MESSAGE})
            if final is not None:
                push(final)
            push(None)
            if slots is not None:
                slots.release()

    try:
        threading.Thread(target=work, name="gift-search", daemon=True).start()
    except BaseException:
        if slots is not None:
            slots.release()
        raise
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                yield sse("error", {"message": TIMEOUT_MESSAGE})
                return
            try:
                item = await asyncio.wait_for(queue.get(), timeout=min(heartbeat_seconds, remaining))
            except asyncio.TimeoutError:
                yield KEEP_ALIVE
                continue
            if item is None:
                return
            yield item
    finally:
        cancelled.set()


def create_app(client_factory: Callable = make_client, max_searches: int = MAX_CONCURRENT_SEARCHES) -> FastAPI:
    slots = threading.BoundedSemaphore(max_searches)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        load_env()  # the server reads the root .env; the browser never sees it
        yield

    app = FastAPI(title="Gift Genius API", lifespan=lifespan)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/api/gift-searches")
    async def start_search(request: SearchRequest) -> StreamingResponse:
        return StreamingResponse(
            search_events(request.description, request.budget, client_factory, slots=slots),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
