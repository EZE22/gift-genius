"""Tool: search_catalog(query, max_price). Keyword search over the catalog."""

from __future__ import annotations

import json
import re

from .catalog import load_catalog

MAX_RESULTS = 8
STOPWORDS = {"a", "an", "and", "the", "for", "of", "to", "with", "or", "in", "on", "gift", "gifts", "who", "likes", "loves"}

SCHEMA = {
    "name": "search_catalog",
    "description": (
        "Search the gift catalog by keywords. Returns up to 8 matching items priced at or "
        "under max_price, best matches first, each with item_id, name, category, price, "
        "description and link. Use a few plain words such as 'coffee grinder' or 'camping'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "A few keywords describing the gift."},
            "max_price": {"type": "number", "description": "Highest price in dollars. Use the budget."},
        },
        "required": ["query", "max_price"],
        "additionalProperties": False,
    },
}


SUFFIXES = ("ing", "es", "ed", "e", "s")


def stem(word: str) -> str:
    """A rough stem so hike, hikes and hiking all match ("hik")."""
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3 and not word.endswith("ss"):
            return word[: -len(suffix)]
    return word


def words(text: str) -> set[str]:
    """Stemmed lowercase words without stopwords."""
    return {stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS}


def search(query: str, max_price: float) -> list[dict]:
    wanted = words(query)
    scored = []
    for item in load_catalog().values():
        if item.price > max_price:
            continue
        score = len(wanted & words(f"{item.name} {item.category} {item.description}"))
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [item.as_dict() for _, item in scored[:MAX_RESULTS]]


def run(tool_input: dict) -> tuple[str, bool]:
    """Returns (result text, is_error)."""
    query = tool_input.get("query")
    max_price = tool_input.get("max_price")
    if not isinstance(query, str) or not query.strip():
        return "query must be a non-empty string.", True
    if isinstance(max_price, bool) or not isinstance(max_price, (int, float)) or max_price <= 0:
        return "max_price must be a positive number of dollars.", True
    results = search(query, float(max_price))
    if not results:
        return f"No items match {query!r} at or under ${max_price:g}. Try other or broader words.", False
    return json.dumps({"results": results}), False
