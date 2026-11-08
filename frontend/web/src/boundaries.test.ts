// The web app talks to the back end only over HTTP at /api, and never holds an API key.
import { describe, expect, it } from "vitest";

const modules = import.meta.glob<string>(["./**/*.ts", "./**/*.tsx", "!./**/*.test.*", "!./test/**"], {
  query: "?raw",
  import: "default",
  eager: true,
});
const files = Object.entries(modules).map(([path, text]) => ({ path, text }));

describe("web boundaries", () => {
  it("reads the app's source files", () => {
    expect(files.map((f) => f.path)).toContain("./api.ts");
  });

  it("only fetches /api paths", () => {
    const urls = files.flatMap(({ text }) => [...text.matchAll(/fetch\(\s*["'`]([^"'`]+)/g)].map((m) => m[1]));
    expect(urls).toEqual(["/api/gift-searches"]);
  });

  it("never imports back end code or mentions API keys", () => {
    for (const { path, text } of files) {
      expect(text, path).not.toMatch(/backend|gift_genius|ANTHROPIC|api[_-]?key|@anthropic-ai/i);
    }
  });
});
