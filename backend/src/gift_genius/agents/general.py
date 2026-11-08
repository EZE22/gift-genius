"""The General specialist: the fallback when the router's label is unknown."""

from .specialist import Specialist

GENERAL = Specialist(
    name="General",
    focus="The request didn't fit one category, so search across tech, outdoors and food gifts and pick what suits this person best.",
)
