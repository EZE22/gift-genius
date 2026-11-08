// Client for the Gift Genius API: POST /api/gift-searches streams Server-Sent Events.

export interface Gift {
  itemId: string;
  name: string;
  price: number;
  link: string;
  reason: string;
}

export interface RemovedGift {
  itemId: string;
  name: string;
  reasons: string[];
}

export interface Shortlist {
  label: string;
  agent: string;
  attempts: number;
  gifts: Gift[];
  removed: RemovedGift[];
  problems: string[];
}

export type GiftEvent =
  | { type: "routed"; label: string; agent: string; fallback: boolean }
  | { type: "searching"; attempt: number; query: string; maxPrice: number; matches: number }
  | { type: "checking"; attempt: number; itemId: string; found: boolean; name: string | null }
  | { type: "validated"; attempt: number; ok: boolean; problems: string[]; willRetry: boolean }
  | { type: "shortlist"; shortlist: Shortlist }
  | { type: "done" }
  | { type: "error"; message: string };

/** Starts a search and calls onEvent for each event until done or error. */
export type StartSearch = (
  request: { description: string; budget: number },
  onEvent: (event: GiftEvent) => void,
  signal: AbortSignal,
) => Promise<void>;

export const NETWORK_ERROR = "Could not reach the Gift Genius server. Check that it's running, then try again.";
export const LOST_ERROR = "The connection to the server was lost before the search finished.";
export const BAD_RESPONSE_ERROR = "The server sent a reply this page couldn't read. Try again.";
export const STALLED_ERROR = "The server stopped responding during the search. Try again.";
export const DEFAULT_SERVER_ERROR = "The search stopped on the server. Try again.";

/** How long the stream may go silent. The server sends a keep-alive every 15 seconds. */
export const STALL_MS = 45_000;

export class ProtocolError extends Error {
  name = "ProtocolError";
}

type Payload = Record<string, unknown>;

const str = (value: unknown): string => (typeof value === "string" ? value : "");
const num = (value: unknown): number => (typeof value === "number" && Number.isFinite(value) ? value : 0);
const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];

/** Only http(s) links are kept, so a bad reply can never produce a javascript: link. */
const safeLink = (value: unknown): string => {
  const link = str(value);
  return /^https?:\/\//i.test(link) ? link : "";
};

function asShortlist(payload: Payload): Shortlist {
  // The server sends snake_case. This is the one place those names become
  // the camelCase fields the rest of the page uses. A gift with no name is
  // dropped rather than rendered as a blank card.
  if (!Array.isArray(payload.gifts)) throw new ProtocolError("shortlist without gifts");
  const gifts = payload.gifts.flatMap((raw) => {
    const g = (raw ?? {}) as Payload;
    const name = str(g.name);
    if (!name) return [];
    return [{ itemId: str(g.item_id), name, price: num(g.price), link: safeLink(g.link), reason: str(g.reason) }];
  });
  const removed = (Array.isArray(payload.removed) ? payload.removed : []).map((raw) => {
    const r = (raw ?? {}) as Payload;
    return { itemId: str(r.item_id), name: str(r.name) || "A gift", reasons: strings(r.reasons) };
  });
  return {
    label: str(payload.label),
    agent: str(payload.agent),
    attempts: num(payload.attempts) || 1,
    gifts,
    removed,
    problems: strings(payload.problems),
  };
}

/** Turns one SSE block ("event: x\ndata: {...}") into a GiftEvent. Throws ProtocolError on bad data. */
export function parseEvent(block: string): GiftEvent | null {
  let name = "";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!name) return null; // a comment such as ": keep-alive"
  let parsed: unknown = {};
  if (data.length) {
    try {
      parsed = JSON.parse(data.join("\n"));
    } catch {
      throw new ProtocolError(`bad JSON in a ${name} event`);
    }
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new ProtocolError(`a ${name} event without an object`);
  }
  const p = parsed as Payload;
  switch (name) {
    case "routed":
      return { type: "routed", label: str(p.label), agent: str(p.agent) || "General", fallback: p.fallback === true };
    case "searching":
      return { type: "searching", attempt: num(p.attempt) || 1, query: str(p.query), maxPrice: num(p.max_price), matches: num(p.matches) };
    case "checking":
      return { type: "checking", attempt: num(p.attempt) || 1, itemId: str(p.item_id), found: p.found === true, name: str(p.name) || null };
    case "validated":
      return { type: "validated", attempt: num(p.attempt) || 1, ok: p.ok === true, problems: strings(p.problems), willRetry: p.will_retry === true };
    case "shortlist":
      return { type: "shortlist", shortlist: asShortlist(p) };
    case "done":
      return { type: "done" };
    case "error":
      return { type: "error", message: str(p.message).trim() || DEFAULT_SERVER_ERROR };
    default:
      return null; // ignore events this version doesn't know
  }
}

/** Accumulates streamed text and emits each complete SSE block. */
export class SseParser {
  private buffer = "";

  constructor(private readonly onEvent: (event: GiftEvent) => void) {}

  feed(chunk: string): void {
    // Chunks are not events. A TCP read can split one event, or hold several.
    // A blank line is the SSE record separator, so only a complete block is parsed.
    this.buffer += chunk.replace(/\r\n/g, "\n");
    let end: number;
    while ((end = this.buffer.indexOf("\n\n")) !== -1) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      this.emit(block);
    }
  }

  end(): void {
    const block = this.buffer.trim();
    this.buffer = "";
    if (block) this.emit(block);
  }

  private emit(block: string): void {
    const event = parseEvent(block);
    if (event) this.onEvent(event);
  }
}

function httpErrorMessage(status: number): string {
  if (status === 422) return "Check the description (up to 1,000 characters) and a budget between $1 and $10,000.";
  if (status >= 500) return "The Gift Genius server isn't responding. Check that it's running, then try again.";
  return `The server returned an unexpected response (${status}). Try again.`;
}

class Stalled extends Error {}

function readWithin<T>(reader: ReadableStreamDefaultReader<T>, ms: number): Promise<ReadableStreamReadResult<T>> {
  // reader.read() has no timeout of its own. Race it against a timer so a
  // stream that goes quiet (no keep-alive, no event) fails instead of hanging.
  let timer: ReturnType<typeof setTimeout> | undefined;
  const stalled = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Stalled()), ms);
  });
  return Promise.race([reader.read(), stalled]).finally(() => clearTimeout(timer));
}

export const startSearch = async (
  request: { description: string; budget: number },
  onEvent: (event: GiftEvent) => void,
  signal: AbortSignal,
  stallMs: number = STALL_MS,
): Promise<void> => {
  // POST the description and budget, then read the response body as a stream
  // of SSE events. The promise resolves when the server sends done or error.
  let response: Response;
  try {
    response = await fetch("/api/gift-searches", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(request),
      signal,
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new Error(NETWORK_ERROR);
  }
  if (!response.ok || !response.body) throw new Error(httpErrorMessage(response.status));
  if (!(response.headers.get("Content-Type") ?? "").includes("text/event-stream")) {
    response.body.cancel().catch(() => {});
    throw new Error(BAD_RESPONSE_ERROR);
  }

  let finished = false;
  const parser = new SseParser((event) => {
    if (finished) return; // nothing counts after done or error
    if (event.type === "done" || event.type === "error") finished = true;
    onEvent(event);
  });
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  try {
    while (!finished) {
      const { value, done } = await readWithin(reader, stallMs);
      if (done) {
        parser.end();
        break;
      }
      parser.feed(value);
    }
  } catch (error) {
    if (signal.aborted) throw error;
    if (finished) return;
    if (error instanceof ProtocolError) throw new Error(BAD_RESPONSE_ERROR);
    if (error instanceof Stalled) throw new Error(STALLED_ERROR);
    throw new Error(LOST_ERROR);
  } finally {
    reader.cancel().catch(() => {});
  }
  if (!finished) throw new Error(LOST_ERROR);
};
