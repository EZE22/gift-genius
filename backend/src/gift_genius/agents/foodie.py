"""The Foodie specialist.

Selected when the router label is "foodie". Same tools and cap as the others;
only the focus line in the system prompt is different.
"""

from .specialist import Specialist

FOODIE = Specialist(
    name="Foodie",
    focus="Look first for cooking, baking, coffee, tea, drinks and specialty food gifts that match this person's taste.",
)
