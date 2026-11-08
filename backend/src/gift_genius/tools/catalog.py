"""Read the gift catalog (data/catalog.json). The tools read only this file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# tools/catalog.py -> gift_genius/tools -> gift_genius/data/catalog.json
CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    category: str
    price: float
    description: str
    link: str

    def as_dict(self) -> dict:
        """The shape the tools hand back to the model. `id` is renamed `item_id`."""
        return {
            "item_id": self.id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "description": self.description,
            "link": self.link,
        }


@lru_cache(maxsize=None)
def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Item]:
    """Every catalog item, keyed by id.

    Cached for the life of the process: the file is the only catalog, and it
    does not change while the server is running. Tests pass a different path
    when they need a different file; that path is part of the cache key.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {row["id"]: Item(**row) for row in data["items"]}
