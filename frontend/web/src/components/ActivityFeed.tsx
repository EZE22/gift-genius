// The live activity list. Each row is one stream event turned into a sentence
// by searchState.feedLine. The last row, while the search is running, is a
// "Working" placeholder that is not part of the stored feed.

import type { FeedItem, Phase } from "../searchState";

const KIND_LABEL = { llm: "LLM call", agent: "Agent", code: "Code", warn: "Code" } as const;

export function ActivityFeed({ feed, phase }: { feed: FeedItem[]; phase: Phase }) {
  return (
    <section className="activity" aria-labelledby="activity-heading">
      <h2 id="activity-heading" className="section-heading">
        Activity
      </h2>
      <ol className="feed" aria-live="polite">
        {feed.map((item) => (
          <li key={item.id} className={`feed-item feed-${item.kind}`}>
            <span className="tag">{KIND_LABEL[item.kind]}</span>
            <div>
              <p>{item.text}</p>
              {item.details && item.details.length > 0 && (
                <ul className="problems">
                  {item.details.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        ))}
        {phase === "running" && (
          <li className="feed-item feed-pending" role="status">
            <span className="tag">Working</span>
            <p>{feed.length === 0 ? "Sorting your request…" : "The agent is choosing its next step…"}</p>
          </li>
        )}
      </ol>
    </section>
  );
}
