import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { GiftEvent, Shortlist, StartSearch } from "./api";
import { App } from "./App";

/** A fake startSearch the test drives: emit events, then finish or fail. */
function fakeSearches() {
  const runs: {
    request: { description: string; budget: number };
    signal: AbortSignal;
    emit: (event: GiftEvent) => void;
    finish: () => Promise<void>;
    fail: (message: string) => Promise<void>;
  }[] = [];
  const startSearch: StartSearch = (request, onEvent, signal) =>
    new Promise<void>((resolve, reject) => {
      runs.push({
        request,
        signal,
        emit: (event) => act(() => onEvent(event)),
        finish: () => act(async () => resolve()),
        fail: (message) => act(async () => reject(new Error(message))),
      });
    });
  return { startSearch, runs, last: () => runs[runs.length - 1] };
}

const GIFTS = [
  { itemId: "out-007", name: "Insulated Water Bottle", price: 28.99, link: "https://gifts.example.com/item/out-007", reason: "Cold water on long hikes." },
  { itemId: "out-006", name: "Headlamp Rechargeable", price: 31.99, link: "https://gifts.example.com/item/out-006", reason: "Lights the trail at dusk." },
  { itemId: "out-012", name: "Bike Multi-Tool", price: 25.99, link: "https://gifts.example.com/item/out-012", reason: "Roadside repairs." },
];
const FULL: Shortlist = { label: "outdoors", agent: "Outdoors", attempts: 1, gifts: GIFTS, removed: [], problems: [] };

async function fillAndSubmit(description = "Loves hiking", budget = "50") {
  const fake = fakeSearches();
  const user = userEvent.setup();
  render(<App startSearch={fake.startSearch} />);
  await user.type(screen.getByLabelText("Who is the gift for?"), description);
  await user.type(screen.getByLabelText("Budget per gift"), budget);
  await user.click(screen.getByRole("button", { name: "Find gifts" }));
  return { ...fake, user };
}

async function runWhole(shortlist: Shortlist = FULL) {
  const ctx = await fillAndSubmit();
  const run = ctx.last();
  run.emit({ type: "routed", label: "outdoors", agent: "Outdoors", fallback: false });
  run.emit({ type: "searching", attempt: 1, query: "hiking", maxPrice: 50, matches: 5 });
  run.emit({ type: "checking", attempt: 1, itemId: "out-007", found: true, name: "Insulated Water Bottle" });
  run.emit({ type: "validated", attempt: 1, ok: true, problems: [], willRetry: false });
  run.emit({ type: "shortlist", shortlist });
  run.emit({ type: "done" });
  await run.finish();
  return ctx;
}

describe("1. empty state and form", () => {
  it("shows how it works before any search", () => {
    render(<App startSearch={fakeSearches().startSearch} />);
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New search" })).not.toBeInTheDocument();
  });

  it("keeps Find gifts disabled until both a description and a valid budget are filled", async () => {
    const user = userEvent.setup();
    render(<App startSearch={fakeSearches().startSearch} />);
    const button = screen.getByRole("button", { name: "Find gifts" });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Who is the gift for?"), "Loves tea");
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Budget per gift"), "abc");
    expect(button).toBeDisabled();
    expect(screen.getByText("Enter a number from 1 to 10,000.")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Budget per gift"));
    await user.type(screen.getByLabelText("Budget per gift"), "$40");
    expect(button).toBeEnabled();
    await user.clear(screen.getByLabelText("Who is the gift for?"));
    await user.type(screen.getByLabelText("Who is the gift for?"), "   ");
    expect(button).toBeDisabled();
  });

  it("sends the trimmed description and the budget as a number", async () => {
    const { runs } = await fillAndSubmit("  Loves hiking  ", "1,200.50");
    expect(runs.map((r) => r.request)).toEqual([{ description: "Loves hiking", budget: 1200.5 }]);
  });

  it("submits with Enter from the budget field", async () => {
    const fake = fakeSearches();
    const user = userEvent.setup();
    render(<App startSearch={fake.startSearch} />);
    await user.type(screen.getByLabelText("Who is the gift for?"), "Loves tea");
    await user.type(screen.getByLabelText("Budget per gift"), "30{Enter}");
    expect(fake.runs).toHaveLength(1);
  });
});

describe("2. loading and the live activity feed", () => {
  it("disables the form and shows progress while running", async () => {
    await fillAndSubmit();
    expect(screen.getByRole("button", { name: "Finding gifts…" })).toBeDisabled();
    expect(screen.getByLabelText("Who is the gift for?")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Sorting your request…");
  });

  it("shows the routing decision and each tool call, tagged by who did it", async () => {
    const { last } = await fillAndSubmit();
    const run = last();
    run.emit({ type: "routed", label: "outdoors", agent: "Outdoors", fallback: false });
    run.emit({ type: "searching", attempt: 1, query: "hiking", maxPrice: 50, matches: 1 });
    run.emit({ type: "checking", attempt: 1, itemId: "out-404", found: false, name: null });
    expect(screen.getByText("Router chose outdoors. Code handed the request to the Outdoors agent.")).toBeInTheDocument();
    expect(screen.getByText('Searched the catalog for "hiking" up to $50.00: 1 match')).toBeInTheDocument();
    expect(screen.getByText("Looked up out-404: not in the catalog")).toBeInTheDocument();
    expect(screen.getByText("LLM call")).toBeInTheDocument();
    expect(screen.getAllByText("Agent")).toHaveLength(2);
    expect(screen.getByRole("status")).toHaveTextContent("choosing its next step");
  });

  it("explains the General fallback", async () => {
    const { last } = await fillAndSubmit();
    last().emit({ type: "routed", label: "books", agent: "General", fallback: true });
    expect(screen.getByText(/answered "books", which isn't a category, so code chose the General agent/)).toBeInTheDocument();
  });

  it("shows a failed check, its problems and the retry", async () => {
    const { last } = await fillAndSubmit();
    const run = last();
    run.emit({ type: "validated", attempt: 1, ok: false, problems: ["Headphones (tech-002): price $188.99 is over the $50.00 budget."], willRetry: true });
    run.emit({ type: "searching", attempt: 2, query: "bike", maxPrice: 50, matches: 3 });
    expect(screen.getByText("Checks failed. Asking the agent to try once more with these problems:")).toBeInTheDocument();
    expect(screen.getByText(/price \$188.99 is over the \$50.00 budget/)).toBeInTheDocument();
    expect(screen.getByText(/^Retry: Searched the catalog for "bike"/)).toBeInTheDocument();
  });
});

describe("3. results", () => {
  it("shows three gift cards with name, price, reason and link, and moves focus to them", async () => {
    await runWhole();
    const heading = screen.getByRole("heading", { name: "Three gift ideas" });
    expect(heading).toHaveFocus();
    const cards = within(screen.getByRole("region", { name: "Three gift ideas" })).getAllByRole("listitem");
    expect(cards).toHaveLength(3);
    expect(within(cards[0]).getByRole("heading", { name: "Insulated Water Bottle" })).toBeInTheDocument();
    expect(within(cards[0]).getByText("$28.99")).toBeInTheDocument();
    expect(within(cards[0]).getByText("Cold water on long hikes.")).toBeInTheDocument();
    const link = within(cards[0]).getByRole("link", { name: /View Insulated Water Bottle/ });
    expect(link).toHaveAttribute("href", "https://gifts.example.com/item/out-007");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Find gifts" })).toBeEnabled();
  });

  it("shows only the gifts that passed and says why the others were removed", async () => {
    await runWhole({
      ...FULL,
      attempts: 2,
      gifts: GIFTS.slice(0, 2),
      removed: [{ itemId: "out-012", name: "Bike Multi-Tool", reasons: ["link 'https://x.test' doesn't match the catalog link"] }],
      problems: ["Bike Multi-Tool (out-012): link 'https://x.test' doesn't match the catalog link."],
    });
    expect(screen.getByRole("heading", { name: "2 gift ideas passed the checks" })).toBeInTheDocument();
    expect(screen.getByText(/on its second try/)).toBeInTheDocument();
    const note = screen.getByRole("note");
    expect(within(note).getByText("Bike Multi-Tool")).toBeInTheDocument();
    expect(within(note).getByText(/doesn't match the catalog link/)).toBeInTheDocument();
  });

  it("lists a count problem that isn't tied to one gift", async () => {
    await runWhole({ ...FULL, attempts: 2, gifts: GIFTS.slice(0, 2), problems: ["Expected exactly 3 gifts but got 2."] });
    expect(within(screen.getByRole("note")).getByText("Expected exactly 3 gifts but got 2.")).toBeInTheDocument();
  });
});

describe("4. errors", () => {
  it("shows a server error event with Try again, which reruns the same request", async () => {
    const { last, runs, user } = await fillAndSubmit();
    last().emit({ type: "error", message: "The Claude API returned an error (529). Try again in a moment." });
    await last().finish();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("The Claude API returned an error (529).");
    expect(alert).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(runs).toHaveLength(2);
    expect(runs[1].request).toEqual(runs[0].request);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a network failure", async () => {
    const { last } = await fillAndSubmit();
    await last().fail("Could not reach the Gift Genius server.");
    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach the Gift Genius server.");
  });
});

describe("5. New search", () => {
  it("resets everything and focuses the description", async () => {
    const { user } = await runWhole();
    await user.click(screen.getByRole("button", { name: "New search" }));
    expect(screen.getByLabelText("Who is the gift for?")).toHaveValue("");
    expect(screen.getByLabelText("Budget per gift")).toHaveValue("");
    expect(screen.queryByRole("heading", { name: "Three gift ideas" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    await act(async () => new Promise((r) => setTimeout(r, 0)));
    expect(screen.getByLabelText("Who is the gift for?")).toHaveFocus();
  });

  it("stops a running search and ignores its late events", async () => {
    const { last, user } = await fillAndSubmit();
    const run = last();
    await user.click(screen.getByRole("button", { name: "New search" }));
    expect(run.signal.aborted).toBe(true);
    run.emit({ type: "routed", label: "tech", agent: "Tech", fallback: false });
    expect(screen.queryByText(/Router chose tech/)).not.toBeInTheDocument();
  });
});
