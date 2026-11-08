# Gift Genius

A routing workflow whose specialists are autonomous agents: describe a person and a budget, a
router picks tech, outdoors or foodie, that specialist searches a 60-item catalog with tools,
and code checks its three picks. React web app and CLI front ends. See README.md for the pattern diagram.

## Structure
```
backend/                  gift-genius-backend (import name gift_genius); [api] extra = FastAPI
  src/gift_genius/        __init__.py (public API), agent.py (generic loop), router.py,
                          orchestrator.py (flow + rules), validation.py (shortlist checks),
                          client.py, errors.py
    agents/               tech.py, outdoors.py, foodie.py, general.py, specialist.py (shared prompt)
    tools/                search_catalog.py, get_item.py, catalog.py (loader)
    api/                  POST /api/gift-searches streams SSE; gift-genius-api command (port 8001)
    data/catalog.json     the only data the tools read
  tests/                  mirrors src/gift_genius/
frontend/web/             gift-genius-web (port 5174, proxies /api to 8001)
frontend/cli/             gift-genius-cli, the gift-genius command
```

Boundaries, enforced by tests:
- The CLI imports only names in `gift_genius.__all__`.
- The web app only talks to the back end over HTTP (`/api`).
- The back end never imports a front end; the API dependencies are an optional extra.
- `.env` stays at the root and is loaded by the back end's `load_env()`. The key never leaves the back end.

Setup: `python3 -m venv .venv`, `.venv/bin/pip install -e "backend[dev]"`, then `-e "frontend/cli[dev]"`; `cd frontend/web && npm install`.
Tests: `cd backend && ../.venv/bin/pytest`, `cd frontend/cli && ../../.venv/bin/pytest`, `cd frontend/web && npm test`.

## Working rules
Follow ~/.claude/CLAUDE.md. Keep TASKS.md current.
