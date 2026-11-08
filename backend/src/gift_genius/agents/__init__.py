"""One file per specialist. Each is a role prompt plus a tool list; agent.py runs them."""

from .foodie import FOODIE
from .general import GENERAL
from .outdoors import OUTDOORS
from .specialist import MAX_TOOL_CALLS, Specialist, first_message
from .tech import TECH

__all__ = ["TECH", "OUTDOORS", "FOODIE", "GENERAL", "Specialist", "MAX_TOOL_CALLS", "first_message"]
