import { afterEach, describe, expect, it, vi } from "vitest";

import {
  BAD_RESPONSE_ERROR,
  LOST_ERROR,
  NETWORK_ERROR,
  STALLED_ERROR,
  SseParser,
  parseEvent,
  startSearch,
  type GiftEvent,
} from "./api";

const block = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

describe("parseEvent", () => {
  it("reads every event kind", () => {
    expect(parseEvent(block("routed", { label: "tech", agent: "Tech", fallback: false }))).toEqual({
      type: "routed", label: "tech", agent: "Tech", fallback: false,
    });
    expect(parseEvent(block("searching", { attempt: 1, query: "tea", max_price: 30, matches: 4 }))).toEqual({
      type: "searching", attempt: 1, query: "tea", maxPrice: 30, matches: 4,
    });
    expect(parseEvent(block("checking", { attempt: 2, item_id: "x", found: false, name: null }))).toEqual({
      type: "checking", attempt: 2, itemId: "x", found: false, name: null,
    });
    expect(parseEvent(block("validated", { attempt: 1, ok: false, problems: ["p"], will_retry: true }))).toEqual({
      type: "validated", attempt: 1, ok: false, problems: ["p"], willRetry: true,
    });
    expect(parseEvent(block("done", {}))).toEqual({ type: "done" });
    expect(parseEvent(block("error", { message: "" }))).toMatchObject({ type: "error" });
    expect(parseEvent(": keep-alive")).toBeNull();
    expect(parseEvent(block("future", {}))).toBeNull();
  });

  it("maps the shortlist and drops unsafe links", () => {
    const event = parseEvent(
      block("shortlist", {
        label: "tech", agent: "Tech", attempts: 1, problems: [],
        gifts: [
          { item_id: "a", name: "A", price: 10, link: "javascript:alert(1)", reason: "r" },
          { item_id: "b", name: "", price: 5 },
        ],
        removed: [{ item_id: "c", name: "C", reasons: ["bad"] }],
      }),
    );
    expect(event).toEqual({
      type: "shortlist",
      shortlist: {
        label: "tech", agent: "Tech", attempts: 1, problems: [],
        gifts: [{ itemId: "a", name: "A", price: 10, link: "", reason: "r" }],
        removed: [{ itemId: "c", name: "C", reasons: ["bad"] }],
      },
    });
  });

  it("throws on broken JSON", () => {
    expect(() => parseEvent("event: done\ndata: {nope")).toThrow();
  });
});

describe("SseParser", () => {
  it("handles events split across chunks and CRLF", () => {
    const seen: GiftEvent[] = [];
    const parser = new SseParser((e) => seen.push(e));
    const text = block("routed", { label: "tech", agent: "Tech", fallback: false }).replace(/\n/g, "\r\n");
    parser.feed(text.slice(0, 10));
    parser.feed(text.slice(10));
    parser.feed("event: done\ndata: {}");
    parser.end();
    expect(seen.map((e) => e.type)).toEqual(["routed", "done"]);
  });
});

function streamResponse(chunks: string[], contentType = "text/event-stream", keepOpen = false) {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(new TextEncoder().encode(c));
      if (!keepOpen) controller.close();
    },
  });
  return new Response(body, { headers: { "Content-Type": contentType } });
}

describe("startSearch", () => {
  afterEach(() => vi.unstubAllGlobals());

  const go = (stallMs?: number) => {
    const events: GiftEvent[] = [];
    const promise = startSearch({ description: "x", budget: 20 }, (e) => events.push(e), new AbortController().signal, stallMs);
    return { events, promise };
  };

  it("posts the request and streams events until done", async () => {
    const fetchMock = vi.fn().mockResolvedValue(streamResponse([block("routed", { label: "tech", agent: "Tech" }), block("done", {})]));
    vi.stubGlobal("fetch", fetchMock);
    const { events, promise } = go();
    await promise;
    expect(events.map((e) => e.type)).toEqual(["routed", "done"]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/gift-searches");
    expect(JSON.parse(init.body)).toEqual({ description: "x", budget: 20 });
  });

  it("reports a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));
    await expect(go().promise).rejects.toThrow(NETWORK_ERROR);
  });

  it("reports a stream that ends early", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(streamResponse([block("routed", { label: "t" })])));
    await expect(go().promise).rejects.toThrow(LOST_ERROR);
  });

  it("reports a non-SSE reply", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(streamResponse(["<html>"], "text/html")));
    await expect(go().promise).rejects.toThrow(BAD_RESPONSE_ERROR);
  });

  it("reports a stalled stream", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(streamResponse([], "text/event-stream", true)));
    await expect(go(20).promise).rejects.toThrow(STALLED_ERROR);
  });

  it("explains a 422", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 422 })));
    await expect(go().promise).rejects.toThrow(/budget between \$1 and \$10,000/);
  });
});
