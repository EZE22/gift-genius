// The web app talks to the back end only over HTTP at /api, and never holds an API key.
// These tests read the source as text. They fail if a fetch URL, an import, or a
// secret name drifts outside that boundary.
import { describe, expect, it } from "vitest";

const modules = import.meta.glob<string>(["./**/*.ts", "./**/*.tsx", "!./**/*.test.*", "!./test/**"], {
  query: "?raw",
  import: "default",
  eager: true,
});
const files = Object.entries(modules).map(([path, text]) => ({ path, text }));

describe("web boundaries", () => {
  it("reads the app's source files", () => {
    // The glob has to see the client, or the later assertions would pass on an empty list.
    expect(files.map((f) => f.path)).toContain("./api.ts");
  });

  it("only fetches /api paths", () => {
    // The only request the page makes is the gift search. The API key stays on the server.
    const urls = files.flatMap(({ text }) => [...text.matchAll(/fetch\(\s*["'`]([^"'`]+)/g)].map((m) => m[1]));
    expect(urls).toEqual(["/api/gift-searches"]);
  });

  it("never imports back end code or mentions API keys", () => {
    // No Python package, no Anthropic SDK, and no key name in the browser bundle's source.
    for (const { path, text } of files) {
      expect(text, path).not.toMatch(/backend|gift_genius|ANTHROPIC|api[_-]?key|@anthropic-ai/i);
    }
  });
});
