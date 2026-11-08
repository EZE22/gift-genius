"""The Tech specialist.

One Specialist value: a display name and a one-line focus. The shared prompt,
tool list and six-call cap all come from specialist.py. orchestrator.pick_agent
selects this object when the router label is "tech".
"""

from .specialist import Specialist

TECH = Specialist(
    name="Tech",
    focus="Look first for gadgets, audio, gaming, cameras, smart home and desk gear that fit how this person spends their time.",
)
