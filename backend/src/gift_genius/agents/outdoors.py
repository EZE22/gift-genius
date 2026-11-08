"""The Outdoors specialist.

Selected when the router label is "outdoors". Same tools and cap as the others;
only the focus line in the system prompt is different.
"""

from .specialist import Specialist

OUTDOORS = Specialist(
    name="Outdoors",
    focus="Look first for hiking, camping, cycling, running, climbing, water sport and gardening gear that fits this person's adventures.",
)
