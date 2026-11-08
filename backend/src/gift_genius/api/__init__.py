"""The Gift Genius HTTP API (FastAPI). Start it with the gift-genius-api command."""

from __future__ import annotations

import os

API_HOST = "127.0.0.1"  # local only: there is no authentication
API_PORT = 8001  # Debate Club's API uses 8000


def main() -> None:
    """Run the API server (the gift-genius-api command)."""
    import uvicorn

    uvicorn.run(
        "gift_genius.api.app:app",
        host=os.environ.get("GIFT_GENIUS_API_HOST", API_HOST),
        port=int(os.environ.get("GIFT_GENIUS_API_PORT", API_PORT)),
    )
