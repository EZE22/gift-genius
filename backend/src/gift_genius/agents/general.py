"""The General specialist: the fallback when the router's label is unknown.

pick_agent returns this for any label other than tech, outdoors or foodie,
including an empty string from a router that refused or was cut off. It still
searches the same catalog with the same two tools; its prompt just does not
favor one category.
"""

from .specialist import Specialist

GENERAL = Specialist(
    name="General",
    focus="The request didn't fit one category, so search across tech, outdoors and food gifts and pick what suits this person best.",
)
