"""Code checks on an agent's shortlist. Nothing the agent says reaches the user unchecked.

The rules: exactly three gifts; every item_id is in the catalog; every price is
at or under the budget; every link matches the catalog. Also: the price must
match the catalog, a gift can't be listed twice, and each gift needs a reason.

Gifts that pass are rebuilt from the catalog (name, price and link come from
the catalog, only the reason from the agent), so the user never sees an
invented detail.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .tools.catalog import Item, load_catalog

EXPECTED_GIFTS = 3
MAX_REASON_LENGTH = 300
PRICE_TOLERANCE = 0.005  # half a cent, for float rounding


@dataclass(frozen=True)
class Gift:
    item_id: str
    name: str
    price: float
    link: str
    reason: str


@dataclass(frozen=True)
class RemovedGift:
    item_id: str
    name: str
    reasons: tuple[str, ...]


@dataclass
class ShortlistCheck:
    passed: list[Gift] = field(default_factory=list)
    removed: list[RemovedGift] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # every failure, worded for the agent's retry

    @property
    def ok(self) -> bool:
        return not self.problems


def parse_shortlist(text: str) -> list | None:
    """The "gifts" list from the agent's reply, or None if the reply isn't that JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if 0 <= start < end:
        candidates.append(cleaned[start : end + 1])  # JSON with a sentence around it
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("gifts"), list):
            return data["gifts"]
        if isinstance(data, list):
            return data
    return None


def _as_price(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None
    return None


def _label(raw: dict, item: Item | None) -> str:
    if item is not None:
        return item.name
    name = raw.get("name")
    return name.strip()[:80] if isinstance(name, str) and name.strip() else "Unnamed gift"


def _check_gift(raw, budget: float, catalog: dict[str, Item], seen: set[str]) -> tuple[Gift | None, RemovedGift | None]:
    if not isinstance(raw, dict):
        return None, RemovedGift("", "Unreadable gift", ("is not a gift object",))
    item_id = raw.get("item_id")
    item_id = item_id.strip() if isinstance(item_id, str) else ""
    item = catalog.get(item_id)
    reasons: list[str] = []

    if item is None:
        reasons.append(f"item_id {item_id or '(missing)'!r} is not in the catalog")
    elif item_id in seen:
        reasons.append("is listed more than once")

    price = _as_price(raw.get("price"))
    if price is None:
        reasons.append("has no price")
    else:
        if price > budget + PRICE_TOLERANCE:
            reasons.append(f"price ${price:.2f} is over the ${budget:.2f} budget")
        if item is not None and abs(price - item.price) > PRICE_TOLERANCE:
            reasons.append(f"price ${price:.2f} doesn't match the catalog price ${item.price:.2f}")
    if item is not None and item.price > budget + PRICE_TOLERANCE and not (price is not None and price > budget + PRICE_TOLERANCE):
        reasons.append(f"catalog price ${item.price:.2f} is over the ${budget:.2f} budget")

    link = raw.get("link")
    if item is not None and link != item.link:
        reasons.append(f"link {link!r} doesn't match the catalog link {item.link}")

    reason = raw.get("reason")
    reason = " ".join(reason.split()) if isinstance(reason, str) else ""
    if not reason:
        reasons.append("has no reason")

    if item_id:
        seen.add(item_id)
    if reasons:
        return None, RemovedGift(item_id, _label(raw, item), tuple(reasons))
    assert item is not None
    return Gift(item.id, item.name, item.price, item.link, reason[:MAX_REASON_LENGTH]), None


def check_shortlist(text: str, budget: float, catalog: dict[str, Item] | None = None) -> ShortlistCheck:
    """Check the agent's final reply against the catalog and the budget."""
    catalog = load_catalog() if catalog is None else catalog
    result = ShortlistCheck()
    gifts = parse_shortlist(text)
    if gifts is None:
        result.problems.append('The reply was not the JSON shortlist: {"gifts": [...]} with three gifts.')
        return result

    if len(gifts) != EXPECTED_GIFTS:
        result.problems.append(f"Expected exactly {EXPECTED_GIFTS} gifts but got {len(gifts)}.")

    seen: set[str] = set()
    for raw in gifts:
        gift, removed = _check_gift(raw, budget, catalog, seen)
        if gift is not None and len(result.passed) >= EXPECTED_GIFTS:
            removed, gift = RemovedGift(gift.item_id, gift.name, ("is beyond the first three gifts",)), None
        if gift is not None:
            result.passed.append(gift)
        else:
            result.removed.append(removed)
            result.problems.append(f"{removed.name} ({removed.item_id or 'no item_id'}): {'; '.join(removed.reasons)}.")
    return result
