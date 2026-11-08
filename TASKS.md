# Tasks

## Done
- [x] User-level ~/.claude/CLAUDE.md written
- [x] Monorepo layout: backend/, frontend/web, frontend/cli, root .env/.env.example/.gitignore
- [x] .env with the API settings copied from ~/projects/debate-club/.env, plus ROUTER_MODEL
- [x] Catalog: 60 made-up gifts (20 tech, 20 outdoors, 20 foodie) in backend/src/gift_genius/data/catalog.json
- [x] Tools: search_catalog(query, max_price), get_item(item_id)
- [x] Router: one call, one label; ROUTER_MODEL falls back to the main model
- [x] Code maps label to agent, with the General fallback
- [x] Four specialists (Tech, Outdoors, Foodie, General), each capped at 6 tool calls
- [x] Shortlist checks: count, catalog ids, budget, links (plus price match, duplicates, missing reason)
- [x] Retry once with the specific problems; on a second failure show passing gifts and why the others were removed
- [x] API: POST /api/gift-searches streams routed, searching, checking, validated, shortlist, done, error
- [x] CLI: gift-genius command
- [x] Web: form with a disabled-until-filled Find gifts button, live activity feed, gift cards, New search, loading/error/phone-width states
- [x] Tests with the model mocked: back end 96, CLI 18, web 28
- [x] Checked in the browser: empty, loading, results, error + Try again, phone width (375px), keyboard use, New search
- [x] Live search in the browser (outdoors, twice) and in the CLI (foodie)
- [x] README with setup and the Pattern section (diagram + legend)
- [x] Comments through backend, frontend/web and frontend/cli explaining what each step does

## Open
- [ ] Set ROUTER_MODEL to a fast model. On Foundry that needs a Claude Haiku 5.5 deployment; until then the router uses the main deployment.
- [ ] Search is plain keyword matching. In the live CLI run the Foodie agent used all 6 tool calls because narrow queries found 1 match each. Consider letting search_catalog filter by category, or return close matches.
- [ ] The General agent only runs when the router replies with something unexpected, since the router is told to pick one of three labels. Decide whether the router should be allowed to answer "other".
- [ ] No automated test runs a real model. Consider a small live smoke test you run by hand.
