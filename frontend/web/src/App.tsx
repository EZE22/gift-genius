// The page. The form lives on the left; the activity feed and results live on
// the right. Search progress arrives as events and is stored by searchState.

import { useEffect, useReducer, useRef, useState } from "react";

import { startSearch as realStartSearch, type StartSearch } from "./api";
import { ActivityFeed } from "./components/ActivityFeed";
import { ErrorPanel } from "./components/ErrorPanel";
import { GiftCards } from "./components/GiftCards";
import { SearchForm, parseBudget } from "./components/SearchForm";
import { initialState, reducer } from "./searchState";

export function App({ startSearch = realStartSearch }: { startSearch?: StartSearch }) {
  // Tests pass their own startSearch so the page never calls the real API.
  const [state, dispatch] = useReducer(reducer, initialState);
  // Description and budget stay in the form until New search clears them.
  // They are not part of the search reducer, which only tracks the stream.
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("");
  // The in-flight request. Aborting it drops late events from a previous search.
  const controller = useRef<AbortController | null>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const resultsRef = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);

  const run = () => {
    const value = parseBudget(budget);
    // The button is disabled in this case. This guard covers Enter on a bad form.
    if (!description.trim() || value === null) return;
    // A second click, or Try again, cancels the search that is already running.
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    dispatch({ type: "start" });
    startSearch(
      { description: description.trim(), budget: value },
      (event) => {
        // Ignore events that arrive after this search was aborted.
        if (!current.signal.aborted) dispatch({ type: "event", event });
      },
      current.signal,
    ).catch((error: unknown) => {
      if (current.signal.aborted) return;
      dispatch({ type: "failed", message: error instanceof Error ? error.message : String(error) });
    });
  };

  const reset = () => {
    // Stop the stream, wipe the feed and the cards, and empty the form.
    controller.current?.abort();
    controller.current = null;
    dispatch({ type: "reset" });
    setDescription("");
    setBudget("");
    // Focus moves after the form is enabled again.
    setTimeout(() => descriptionRef.current?.focus(), 0);
  };

  useEffect(() => () => controller.current?.abort(), []);

  // Move focus to what just appeared, so keyboard and screen reader users land on it.
  useEffect(() => {
    if (state.phase === "done") resultsRef.current?.focus();
    if (state.phase === "error") errorRef.current?.focus();
  }, [state.phase]);

  const busy = state.phase === "running";
  const started = state.phase !== "idle";

  return (
    <main className="page">
      <header className="masthead">
        <h1>Gift Genius</h1>
        <p className="lede">
          Describe someone and set a budget. A router picks a specialist, the specialist searches the catalog, and code
          checks every suggestion before you see it.
        </p>
      </header>

      <div className="layout">
        <div className="column">
          <SearchForm
            ref={descriptionRef}
            description={description}
            budget={budget}
            busy={busy}
            onDescription={setDescription}
            onBudget={setBudget}
            onSubmit={run}
          />
          {started && (
            <button type="button" className="secondary new-search" onClick={reset}>
              New search
            </button>
          )}
        </div>

        <div className="column wide">
          {!started && (
            <div className="empty">
              <h2 className="section-heading">How it works</h2>
              <ol>
                <li>One quick model call labels the request: tech, outdoors or foodie.</li>
                <li>Code hands it to that specialist agent, which searches the catalog with up to six tool calls.</li>
                <li>Code checks the three picks: real catalog items, within budget, correct links. One retry if not.</li>
              </ol>
            </div>
          )}
          {started && <ActivityFeed feed={state.feed} phase={state.phase} />}
          {state.phase === "error" && state.error && <ErrorPanel ref={errorRef} message={state.error} onRetry={run} />}
          {state.shortlist && state.phase !== "error" && (
            <GiftCards ref={resultsRef} shortlist={state.shortlist} />
          )}
        </div>
      </div>
    </main>
  );
}
