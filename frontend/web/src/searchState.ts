// The page's state: idle -> running -> done | error. Events from the stream drive it.

import type { GiftEvent, Shortlist } from "./api";

export type Phase = "idle" | "running" | "done" | "error";

export type FeedKind = "llm" | "code" | "agent" | "warn";

export interface FeedItem {
  id: number;
  kind: FeedKind; // what did the step: one LLM call, an agent's tool call, or code
  text: string;
  details?: string[];
}

export interface SearchState {
  phase: Phase;
  feed: FeedItem[];
  shortlist: Shortlist | null;
  error: string | null;
}

export const initialState: SearchState = { phase: "idle", feed: [], shortlist: null, error: null };

export type Action =
  | { type: "start" }
  | { type: "event"; event: GiftEvent }
  | { type: "failed"; message: string }
  | { type: "reset" };

export const money = (value: number): string =>
  value.toLocaleString("en-US", { style: "currency", currency: "USD" });

const retryMark = (attempt: number) => (attempt > 1 ? "Retry: " : "");

/** One feed line per event, or null for events shown elsewhere. */
export function feedLine(event: GiftEvent): Omit<FeedItem, "id"> | null {
  switch (event.type) {
    case "routed":
      return event.fallback
        ? { kind: "llm", text: `Router answered "${event.label}", which isn't a category, so code chose the General agent.` }
        : { kind: "llm", text: `Router chose ${event.label}. Code handed the request to the ${event.agent} agent.` };
    case "searching":
      return {
        kind: "agent",
        text: `${retryMark(event.attempt)}Searched the catalog for "${event.query}" up to ${money(event.maxPrice)}: ${event.matches} ${event.matches === 1 ? "match" : "matches"}`,
      };
    case "checking":
      return {
        kind: "agent",
        text: event.found
          ? `${retryMark(event.attempt)}Looked up ${event.name ?? event.itemId}`
          : `${retryMark(event.attempt)}Looked up ${event.itemId}: not in the catalog`,
      };
    case "validated":
      if (event.ok) return { kind: "code", text: `${retryMark(event.attempt)}Checks passed: three catalog gifts, under budget, with catalog links.` };
      return {
        kind: "warn",
        text: event.willRetry
          ? "Checks failed. Asking the agent to try once more with these problems:"
          : "Checks failed again. Showing only the gifts that passed.",
        details: event.problems,
      };
    default:
      return null;
  }
}

export function reducer(state: SearchState, action: Action): SearchState {
  // Pure: the same action on the same state always returns the same next state.
  // The page dispatches one action per stream event, plus start, reset and failed.
  switch (action.type) {
    case "start":
      // A new search drops the previous feed, cards and error.
      return { ...initialState, phase: "running" };
    case "reset":
      return initialState;
    case "failed":
      // A network failure after the stream already finished is ignored.
      return state.phase === "running" ? { ...state, phase: "error", error: action.message } : state;
    case "event": {
      if (state.phase !== "running") return state; // a late event from a search that was reset
      const { event } = action;
      // The shortlist is stored for the cards. The feed does not repeat it.
      if (event.type === "shortlist") return { ...state, shortlist: event.shortlist };
      if (event.type === "done") return { ...state, phase: "done" };
      if (event.type === "error") return { ...state, phase: "error", error: event.message };
      const line = feedLine(event);
      if (!line) return state;
      return { ...state, feed: [...state.feed, { id: state.feed.length + 1, ...line }] };
    }
  }
}
