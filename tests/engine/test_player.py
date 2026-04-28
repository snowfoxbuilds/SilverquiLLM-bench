"""Tests for engine/player.py — Player ABC and DeterministicPlayer.

Verifies:
- Player ABC cannot be instantiated directly.
- DeterministicPlayer construction with name and script.
- Default property values: life=20, has_lost=False, land_plays_remaining=1, zones initialized, mana_pool=None.
- Each abstract method (choose_target, choose, choose_yes_no, assign_damage_order, choose_card)
  pops from script and returns the correct value.
- Script drains in FIFO order across different method calls.
- remaining_choices property tracks remaining items accurately.
- ScriptExhaustedError raised when script is empty and a method is called.
- Multiple sequential calls drain the queue correctly.
- Edge case: empty script raises on first call.
- Edge case: script with exactly one item — works once, fails on second call.
"""

from __future__ import annotations

import pytest

from engine.player import DeterministicPlayer, Player, ScriptExhaustedError
from engine.zones import Zones


# ---------------------------------------------------------------------------
# Player ABC — cannot be instantiated
# ---------------------------------------------------------------------------
class TestPlayerABC:
    """Tests for the Player abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Player is abstract and should raise TypeError on direct instantiation."""
        with pytest.raises(TypeError):
            Player("test")  # type: ignore[abstract]

    def test_player_is_abstract_with_all_five_methods(self) -> None:
        """Player should declare exactly the 5 required abstract methods."""
        abstract_methods = getattr(Player, "__abstractmethods__", frozenset())
        expected = {"choose_target", "choose", "choose_yes_no", "assign_damage_order", "choose_card"}
        assert abstract_methods == expected


# ---------------------------------------------------------------------------
# DeterministicPlayer — construction and default properties
# ---------------------------------------------------------------------------
class TestDeterministicPlayerConstruction:
    """Tests for DeterministicPlayer construction and inherited default properties."""

    def test_name_stored(self) -> None:
        """Constructor should store the player's name."""
        p = DeterministicPlayer("Alice", [])
        assert p.name == "Alice"

    def test_default_life_is_20(self) -> None:
        """Default life total should be 20."""
        p = DeterministicPlayer("Alice", [])
        assert p.life == 20

    def test_custom_life(self) -> None:
        """Player can be initialized with a custom life total."""
        p = DeterministicPlayer("Bob", [], life=40)
        assert p.life == 40

    def test_has_lost_defaults_false(self) -> None:
        """has_lost should default to False."""
        p = DeterministicPlayer("Alice", [])
        assert p.has_lost is False

    def test_land_plays_remaining_defaults_1(self) -> None:
        """land_plays_remaining should default to 1."""
        p = DeterministicPlayer("Alice", [])
        assert p.land_plays_remaining == 1

    def test_zones_initialized_as_zones_object(self) -> None:
        """zones should be initialized as a Zones instance."""
        p = DeterministicPlayer("Alice", [])
        assert isinstance(p.zones, Zones)

    def test_mana_pool_defaults_none(self) -> None:
        """mana_pool should default to None (forward ref, not yet implemented)."""
        p = DeterministicPlayer("Alice", [])
        assert p.mana_pool is None

    def test_each_player_gets_distinct_zones(self) -> None:
        """Two players should not share the same Zones instance."""
        p1 = DeterministicPlayer("P1", [])
        p2 = DeterministicPlayer("P2", [])
        assert p1.zones is not p2.zones

    def test_remaining_choices_matches_script_length(self) -> None:
        """remaining_choices should reflect the initial script length."""
        p = DeterministicPlayer("Alice", ["a", "b", "c"])
        assert p.remaining_choices == 3


# ---------------------------------------------------------------------------
# DeterministicPlayer — each abstract method pops and returns correctly
# ---------------------------------------------------------------------------
class TestDeterministicPlayerMethods:
    """Verify each abstract method pops from the script and returns the correct value."""

    def test_choose_target_returns_scripted_value(self) -> None:
        """choose_target should pop and return the front of the script."""
        p = DeterministicPlayer("Alice", ["target_a"])
        result = p.choose_target(["target_a", "target_b"], "some requirement")
        assert result == "target_a"

    def test_choose_returns_scripted_value(self) -> None:
        """choose should pop and return the front of the script."""
        p = DeterministicPlayer("Alice", ["option_1"])
        result = p.choose(["option_1", "option_2"], "pick one")
        assert result == "option_1"

    def test_choose_yes_no_returns_scripted_bool(self) -> None:
        """choose_yes_no should pop and return a boolean from the script."""
        p = DeterministicPlayer("Alice", [True])
        result = p.choose_yes_no("Do thing?")
        assert result is True

    def test_choose_yes_no_returns_false(self) -> None:
        """choose_yes_no should return False when scripted."""
        p = DeterministicPlayer("Alice", [False])
        result = p.choose_yes_no("Another?")
        assert result is False

    def test_assign_damage_order_returns_scripted_list(self) -> None:
        """assign_damage_order should pop and return the scripted ordering."""
        order = [3, 1, 2]
        p = DeterministicPlayer("Alice", [order])
        result = p.assign_damage_order([1, 2, 3])
        assert result == [3, 1, 2]

    def test_choose_card_returns_scripted_value(self) -> None:
        """choose_card should pop and return the scripted card."""
        p = DeterministicPlayer("Alice", ["Lightning Bolt"])
        result = p.choose_card(["Lightning Bolt", "Counterspell"], "choose a card")
        assert result == "Lightning Bolt"

    def test_method_decrements_remaining_choices(self) -> None:
        """Each method call should decrement remaining_choices by 1."""
        p = DeterministicPlayer("Alice", ["a", "b"])
        assert p.remaining_choices == 2
        p.choose([], "")
        assert p.remaining_choices == 1
        p.choose_target([], None)
        assert p.remaining_choices == 0


# ---------------------------------------------------------------------------
# DeterministicPlayer — FIFO order across mixed method calls
# ---------------------------------------------------------------------------
class TestDeterministicPlayerFIFO:
    """Verify that the script drains in FIFO order regardless of which method is called."""

    def test_fifo_across_different_methods(self) -> None:
        """Answers should be consumed in FIFO order even when calling different methods."""
        p = DeterministicPlayer("Alice", ["first", "second", "third", "fourth", "fifth"])
        assert p.choose([], "a") == "first"
        assert p.choose_target([], None) == "second"
        assert p.choose_yes_no("q?") == "third"
        assert p.assign_damage_order([]) == "fourth"
        assert p.choose_card([], "c") == "fifth"

    def test_fifo_multiple_calls_to_same_method(self) -> None:
        """Multiple calls to the same method should still drain in order."""
        p = DeterministicPlayer("Alice", [10, 20, 30])
        assert p.choose([], "") == 10
        assert p.choose([], "") == 20
        assert p.choose([], "") == 30

    def test_fifo_with_heterogeneous_types(self) -> None:
        """Script can hold different types; they come out in insertion order."""
        script = ["string_val", 42, True, [1, 2, 3], {"key": "value"}]
        p = DeterministicPlayer("Alice", script)
        assert p.choose([], "") == "string_val"
        assert p.choose([], "") == 42
        assert p.choose_yes_no("") is True
        assert p.choose([], "") == [1, 2, 3]
        assert p.choose([], "") == {"key": "value"}
        assert p.remaining_choices == 0


# ---------------------------------------------------------------------------
# DeterministicPlayer — remaining_choices tracking
# ---------------------------------------------------------------------------
class TestDeterministicPlayerRemainingChoices:
    """Verify remaining_choices property tracks the number of scripted answers left."""

    def test_remaining_decrements_on_each_call(self) -> None:
        """remaining_choices should decrement by 1 for each method call."""
        p = DeterministicPlayer("Alice", [1, 2, 3, 4, 5])
        for expected in [5, 4, 3, 2, 1]:
            assert p.remaining_choices == expected
            p.choose([], "")
        assert p.remaining_choices == 0

    def test_remaining_choices_zero_on_empty_script(self) -> None:
        """An empty script should start with remaining_choices == 0."""
        p = DeterministicPlayer("Alice", [])
        assert p.remaining_choices == 0


# ---------------------------------------------------------------------------
# DeterministicPlayer — ScriptExhaustedError
# ---------------------------------------------------------------------------
class TestScriptExhaustedError:
    """Verify ScriptExhaustedError is raised when the script runs out."""

    def test_empty_script_raises_on_choose(self) -> None:
        """Empty script should raise ScriptExhaustedError on the first call to choose."""
        p = DeterministicPlayer("Alice", [])
        with pytest.raises(ScriptExhaustedError):
            p.choose([], "nothing left")

    def test_empty_script_raises_on_choose_target(self) -> None:
        """Empty script should raise ScriptExhaustedError on choose_target."""
        p = DeterministicPlayer("Alice", [])
        with pytest.raises(ScriptExhaustedError):
            p.choose_target([], None)

    def test_empty_script_raises_on_choose_yes_no(self) -> None:
        """Empty script should raise ScriptExhaustedError on choose_yes_no."""
        p = DeterministicPlayer("Alice", [])
        with pytest.raises(ScriptExhaustedError):
            p.choose_yes_no("question?")

    def test_empty_script_raises_on_assign_damage_order(self) -> None:
        """Empty script should raise ScriptExhaustedError on assign_damage_order."""
        p = DeterministicPlayer("Alice", [])
        with pytest.raises(ScriptExhaustedError):
            p.assign_damage_order([])

    def test_empty_script_raises_on_choose_card(self) -> None:
        """Empty script should raise ScriptExhaustedError on choose_card."""
        p = DeterministicPlayer("Alice", [])
        with pytest.raises(ScriptExhaustedError):
            p.choose_card([], "pick")

    def test_script_exhausted_is_exception_subclass(self) -> None:
        """ScriptExhaustedError should be a subclass of Exception."""
        assert issubclass(ScriptExhaustedError, Exception)

    def test_single_item_script_works_once_then_raises(self) -> None:
        """A script with exactly one item should work on first call, raise on second."""
        p = DeterministicPlayer("Alice", ["only_answer"])
        result = p.choose([], "first call")
        assert result == "only_answer"
        assert p.remaining_choices == 0
        with pytest.raises(ScriptExhaustedError):
            p.choose([], "second call")

    def test_exhausted_after_full_drain(self) -> None:
        """After draining all items, any method should raise ScriptExhaustedError."""
        p = DeterministicPlayer("Alice", ["a", "b"])
        p.choose([], "")
        p.choose([], "")
        with pytest.raises(ScriptExhaustedError):
            p.choose_target([], None)

    def test_script_not_mutated_after_exhaustion(self) -> None:
        """After ScriptExhaustedError, remaining_choices should still be 0."""
        p = DeterministicPlayer("Alice", [])
        with pytest.raises(ScriptExhaustedError):
            p.choose([], "")
        assert p.remaining_choices == 0


# ---------------------------------------------------------------------------
# DeterministicPlayer — original script list is not shared
# ---------------------------------------------------------------------------
class TestDeterministicPlayerScriptIsolation:
    """Verify that the constructor copies the script so external mutation doesn't affect player."""

    def test_external_list_mutation_does_not_affect_player(self) -> None:
        """Modifying the original list after construction should not affect the player."""
        original = ["a", "b", "c"]
        p = DeterministicPlayer("Alice", original)
        original.clear()  # Mutate the original list
        assert p.remaining_choices == 3
        assert p.choose([], "") == "a"
