import { useEffect, useReducer, useRef, useState } from "react";

import { startSearch as realStartSearch, type StartSearch } from "./api";
import { ActivityFeed } from "./components/ActivityFeed";
import { ErrorPanel } from "./components/ErrorPanel";
import { GiftCards } from "./components/GiftCards";
import { SearchForm, parseBudget } from "./components/SearchForm";
import { initialState, reducer } from "./searchState";

export function App({ startSearch = realStartSearch }: { startSearch?: StartSearch }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("");
  const controller = useRef<AbortController | null>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const resultsRef = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);

  const run = () => {
    const value = parseBudget(budget);
    if (!description.trim() || value === null) return;
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    dispatch({ type: "start" });
    startSearch(
      { description: description.trim(), budget: value },
      (event) => {
        if (!current.signal.aborted) dispatch({ type: "event", event });
      },
      current.signal,
    ).catch((error: unknown) => {
      if (current.signal.aborted) return;
      dispatch({ type: "failed", message: error instanceof Error ? error.message : String(error) });
    });
  };

  const reset = () => {
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
