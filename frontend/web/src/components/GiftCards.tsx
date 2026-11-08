// The result cards. Names, prices and links are the ones the server rebuilt
// from the catalog. A shortlist that failed twice still renders the gifts
// that passed, then a note listing what was removed and why.

import { forwardRef } from "react";

import type { Shortlist } from "../api";
import { money } from "../searchState";

export const GiftCards = forwardRef<HTMLHeadingElement, { shortlist: Shortlist }>(function GiftCards(
  { shortlist },
  headingRef,
) {
  const { gifts, removed, problems } = shortlist;
  // problems is empty only when every check passed. Otherwise the heading
  // counts the gifts that survived, which may be fewer than three.
  const complete = problems.length === 0;
  const heading = complete
    ? "Three gift ideas"
    : gifts.length === 0
      ? "No gift ideas passed the checks"
      : `${gifts.length} gift ${gifts.length === 1 ? "idea" : "ideas"} passed the checks`;
  // Per-gift failures are already listed under `removed`. This keeps the
  // shortlist-wide ones, such as "expected exactly 3 gifts".
  const otherProblems = problems.filter((p) => !removed.some((r) => p.startsWith(`${r.name} (`)));

  return (
    <section className="results" aria-labelledby="results-heading">
      <h2 id="results-heading" className="section-heading" tabIndex={-1} ref={headingRef}>
        {heading}
      </h2>
      <p className="muted">
        From the {shortlist.agent} agent
        {shortlist.attempts > 1 ? ", on its second try" : ""}. Names, prices and links come from the catalog.
      </p>
      {gifts.length > 0 && (
        <ul className="cards">
          {gifts.map((gift) => (
            <li key={gift.itemId} className="card">
              <h3>{gift.name}</h3>
              <p className="price">{money(gift.price)}</p>
              <p className="reason">{gift.reason}</p>
              {gift.link && (
                <a href={gift.link} target="_blank" rel="noopener noreferrer">
                  View {gift.name}
                  <span className="visually-hidden"> (opens in a new tab)</span>
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
      {!complete && (
        <div className="removed" role="note">
          <h3>Why some suggestions were removed</h3>
          <p>The agent had two tries. These didn't pass the checks:</p>
          <ul>
            {removed.map((r) => (
              <li key={`${r.itemId}-${r.name}`}>
                <strong>{r.name}</strong>: {r.reasons.join("; ")}
              </li>
            ))}
            {otherProblems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
});
