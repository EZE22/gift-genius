"""Tool: get_item(item_id). Look up one catalog item by id."""

from __future__ import annotations

import json

from .catalog import load_catalog

SCHEMA = {
    "name": "get_item",
    "description": "Get one catalog item by its item_id, with its exact name, price, description and link.",
    "input_schema": {
        "type": "object",
        "properties": {"item_id": {"type": "string", "description": "An item_id from search_catalog, e.g. tech-004."}},
        "required": ["item_id"],
        "additionalProperties": False,
    },
}


def run(tool_input: dict) -> tuple[str, bool]:
    """Look up one id. Returns (JSON for the model, is_error).

    A missing or unknown id is an error. The model is told to take the id from
    a search result rather than invent one.
    """
    item_id = tool_input.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        return "item_id must be a non-empty string.", True
    item = load_catalog().get(item_id.strip())
    if item is None:
        return f"No item has item_id {item_id!r}. Use an item_id from search_catalog.", True
    return json.dumps(item.as_dict()), False
