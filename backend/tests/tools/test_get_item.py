"""get_item returns one catalog row as JSON, or an error the model can read."""

import json

from gift_genius.tools import get_item


def test_returns_the_item():
    """A known id comes back as JSON with is_error False."""
    content, is_error = get_item.run({"item_id": "tech-001"})
    assert not is_error
    assert json.loads(content)["name"] == "Pocket Bluetooth Speaker"


def test_unknown_id_is_an_error():
    """An id that is not in the catalog is an error, and the message says so."""
    content, is_error = get_item.run({"item_id": "tech-999"})
    assert is_error and "No item has item_id" in content


def test_missing_id_is_an_error():
    """A call with no item_id is an error rather than a lookup of an empty string."""
    assert get_item.run({})[1]
