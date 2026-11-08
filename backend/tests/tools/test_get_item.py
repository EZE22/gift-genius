import json

from gift_genius.tools import get_item


def test_returns_the_item():
    content, is_error = get_item.run({"item_id": "tech-001"})
    assert not is_error
    assert json.loads(content)["name"] == "Pocket Bluetooth Speaker"


def test_unknown_id_is_an_error():
    content, is_error = get_item.run({"item_id": "tech-999"})
    assert is_error and "No item has item_id" in content


def test_missing_id_is_an_error():
    assert get_item.run({})[1]
