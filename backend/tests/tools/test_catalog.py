"""The catalog file is the only data the tools read: about 60 gifts, three categories."""

from gift_genius.tools.catalog import load_catalog


def test_catalog_has_about_sixty_gifts_across_three_categories():
    """Every item has a unique id, a price, a description, and a link built from that id."""
    items = list(load_catalog().values())
    assert 55 <= len(items) <= 65
    assert {i.category for i in items} == {"tech", "outdoors", "foodie"}
    for item in items:
        assert item.name and item.description and item.price > 0
        assert item.link == f"https://gifts.example.com/item/{item.id}"
    assert len({i.id for i in items}) == len(items)
