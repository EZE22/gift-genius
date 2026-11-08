"""The specialists' tools. Each module has a SCHEMA and a run(input) -> (text, is_error)."""

from __future__ import annotations

from . import get_item, search_catalog

TOOLS = {search_catalog.SCHEMA["name"]: search_catalog, get_item.SCHEMA["name"]: get_item}
SCHEMAS = [search_catalog.SCHEMA, get_item.SCHEMA]


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    tool = TOOLS.get(name)
    if tool is None:
        return f"Unknown tool {name!r}.", True
    if not isinstance(tool_input, dict):
        return "Tool input must be an object.", True
    return tool.run(tool_input)
