"""Gift Genius back end: route a gift request to a specialist agent and check its shortlist.

This module is the back end's public API. Front ends import only the names in
__all__; everything in submodules is internal and may change.
"""

from .client import ConfigError, Settings, load_env, make_client
from .errors import describe_error
from .orchestrator import (
    CHECKING,
    MAX_BUDGET,
    MAX_DESCRIPTION_LENGTH,
    ROUTED,
    SEARCHING,
    SHORTLIST,
    VALIDATED,
    GiftError,
    GiftResult,
    find_gifts,
)
from .validation import Gift, RemovedGift

__all__ = [
    # Setup
    "load_env",
    "make_client",
    "Settings",
    "ConfigError",
    # Running a search
    "find_gifts",
    "GiftResult",
    "Gift",
    "RemovedGift",
    "GiftError",
    "describe_error",
    "MAX_BUDGET",
    "MAX_DESCRIPTION_LENGTH",
    # Event kinds passed to find_gifts's on_event(kind, data)
    "ROUTED",
    "SEARCHING",
    "CHECKING",
    "VALIDATED",
    "SHORTLIST",
]
