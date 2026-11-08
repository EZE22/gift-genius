"""The specialists' tools. Each module has a SCHEMA and a run(input) -> (text, is_error)."""

from __future__ import annotations

from . import get_item, search_catalog

TOOLS = {search_catalog.SCHEMA["name"]: search_catalog, get_item.SCHEMA["name"]: get_item}
SCHEMAS = [search_catalog.SCHEMA, get_item.SCHEMA]


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Dispatch one tool call. Unknown names and non-object input are errors.

    The loop in agent.py treats the second value as the API's is_error flag,
    so a bad call comes back to the model as a failed tool result rather than
    raising.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return f"Unknown tool {name!r}.", True
    if not isinstance(tool_input, dict):
        return "Tool input must be an object.", True
    return tool.run(tool_input)
