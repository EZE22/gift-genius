"""Each specialist is a name, a focus line, and the two catalog tools. The cap is six."""

from gift_genius.agents import FOODIE, GENERAL, MAX_TOOL_CALLS, OUTDOORS, TECH, first_message


def test_each_specialist_has_its_role_and_both_tools():
    """Every specialist introduces itself, offers both tools, and is told to return three gifts."""
    for agent in (TECH, OUTDOORS, FOODIE, GENERAL):
        assert agent.system.startswith(f"You are the {agent.name} gift specialist")
        assert [s["name"] for s in agent.tool_schemas] == ["search_catalog", "get_item"]
        assert '"gifts"' in agent.system and "exactly three" in agent.system
    assert MAX_TOOL_CALLS == 6


def test_first_message_wraps_the_description_and_lists_retry_problems():
    """The first prompt has the budget and the description. A retry adds the failed checks."""
    plain = first_message("Loves tea", 25)
    assert "Budget: $25.00" in plain and "<description>\nLoves tea\n</description>" in plain
    assert "previous shortlist" not in plain
    retry = first_message("Loves tea", 25, ["Gift X: link is wrong."])
    assert "- Gift X: link is wrong." in retry
