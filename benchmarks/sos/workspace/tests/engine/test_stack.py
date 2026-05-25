"""Tests for engine/stack.py — Stack, StackObject, and priority_loop.

Verifies:
- StackObject dataclass construction and defaults.
- Stack push/pop/peek/is_empty/objects methods.
- LIFO resolution order.
- priority_loop with empty stack (auto-pass, returns immediately).
- priority_loop with items on stack (resolves in LIFO order).
- priority_loop with DeterministicPlayer scripts for priority passing.
- Mana abilities resolve immediately without using the stack.
- check_state_based_actions stub is callable.
- GameState.stack is initialized as a Stack instance.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.stack import Stack, StackObject, check_state_based_actions, priority_loop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_game(p1_script: list | None = None, p2_script: list | None = None) -> GameState:
    """Create a 2-player GameState with optional scripts for DeterministicPlayers."""
    p1 = DeterministicPlayer("Alice", p1_script or [])
    p2 = DeterministicPlayer("Bob", p2_script or [])
    return GameState([p1, p2])


def _make_stack_object(
    game: GameState,
    *,
    label: str = "spell",
    on_resolve=None,
    is_mana_ability: bool = False,
) -> StackObject:
    """Create a StackObject controlled by the active player."""
    return StackObject(
        source=label,
        controller=game.active_player,
        on_resolve=on_resolve or (lambda _g: None),
        is_mana_ability=is_mana_ability,
    )


def _make_resolver(label: str, resolved: list[str]):
    """Return an on_resolve callback that appends *label* to *resolved*."""
    return lambda g: resolved.append(label)


# ===========================================================================
# StackObject dataclass
# ===========================================================================
class TestStackObject:
    """Tests for StackObject construction and defaults."""

    def test_construction_with_all_fields(self) -> None:
        """StackObject should store all explicitly provided fields."""
        game = _make_game()
        callback = lambda g: None
        obj = StackObject(
            source="Lightning Bolt",
            controller=game.active_player,
            targets=["target1"],
            on_resolve=callback,
            is_mana_ability=False,
        )
        assert obj.source == "Lightning Bolt"
        assert obj.controller is game.active_player
        assert obj.targets == ["target1"]
        assert obj.on_resolve is callback
        assert obj.is_mana_ability is False

    def test_default_targets_empty_list(self) -> None:
        """targets should default to an empty list."""
        game = _make_game()
        obj = StackObject(source="x", controller=game.active_player)
        assert obj.targets == []

    def test_default_is_mana_ability_false(self) -> None:
        """is_mana_ability should default to False."""
        game = _make_game()
        obj = StackObject(source="x", controller=game.active_player)
        assert obj.is_mana_ability is False

    def test_default_on_resolve_callable(self) -> None:
        """Default on_resolve should be callable without error."""
        game = _make_game()
        obj = StackObject(source="x", controller=game.active_player)
        obj.on_resolve(game)  # Should not raise
        assert callable(obj.on_resolve)

    def test_targets_default_is_independent(self) -> None:
        """Each StackObject should get its own independent targets list (no shared mutable default)."""
        game = _make_game()
        a = StackObject(source="a", controller=game.active_player)
        b = StackObject(source="b", controller=game.active_player)
        a.targets.append("t")
        assert b.targets == []

    def test_is_mana_ability_true(self) -> None:
        """is_mana_ability can be set to True for mana abilities."""
        game = _make_game()
        obj = StackObject(source="Llanowar Elves", controller=game.active_player, is_mana_ability=True)
        assert obj.is_mana_ability is True


# ===========================================================================
# Stack data structure
# ===========================================================================
class TestStack:
    """Tests for the Stack container (LIFO data structure)."""

    def test_new_stack_is_empty(self) -> None:
        """A freshly constructed Stack should report empty."""
        s = Stack()
        assert s.is_empty()

    def test_push_makes_non_empty(self) -> None:
        """Pushing an object should make is_empty() return False."""
        game = _make_game()
        s = Stack()
        s.push(_make_stack_object(game, label="A"))
        assert not s.is_empty()

    def test_pop_returns_last_pushed(self) -> None:
        """pop() should return the most recently pushed object (LIFO)."""
        game = _make_game()
        s = Stack()
        a = _make_stack_object(game, label="A")
        b = _make_stack_object(game, label="B")
        s.push(a)
        s.push(b)
        assert s.pop() is b

    def test_pop_lifo_order_three_items(self) -> None:
        """Popping all three items should yield them in LIFO order."""
        game = _make_game()
        s = Stack()
        a = _make_stack_object(game, label="A")
        b = _make_stack_object(game, label="B")
        c = _make_stack_object(game, label="C")
        s.push(a)
        s.push(b)
        s.push(c)
        assert s.pop() is c
        assert s.pop() is b
        assert s.pop() is a

    def test_pop_empty_raises_index_error(self) -> None:
        """Popping an empty stack should raise IndexError."""
        s = Stack()
        with pytest.raises(IndexError):
            s.pop()

    def test_peek_returns_top_without_removal(self) -> None:
        """peek() should return the top item without removing it."""
        game = _make_game()
        s = Stack()
        a = _make_stack_object(game, label="A")
        s.push(a)
        assert s.peek() is a
        assert not s.is_empty()  # Still present

    def test_peek_empty_returns_none(self) -> None:
        """peek() on an empty stack should return None."""
        s = Stack()
        assert s.peek() is None

    def test_peek_after_two_pushes_returns_top(self) -> None:
        """peek() should return the second pushed item (the top of stack)."""
        game = _make_game()
        s = Stack()
        a = _make_stack_object(game, label="A")
        b = _make_stack_object(game, label="B")
        s.push(a)
        s.push(b)
        assert s.peek() is b

    def test_objects_top_to_bottom_order(self) -> None:
        """objects() should return items ordered from top (most recent) to bottom."""
        game = _make_game()
        s = Stack()
        a = _make_stack_object(game, label="A")
        b = _make_stack_object(game, label="B")
        c = _make_stack_object(game, label="C")
        s.push(a)
        s.push(b)
        s.push(c)
        result = s.objects()
        assert result[0] is c  # top
        assert result[1] is b
        assert result[2] is a  # bottom

    def test_objects_returns_defensive_copy(self) -> None:
        """objects() should return a new list — mutating it must not affect the stack."""
        game = _make_game()
        s = Stack()
        s.push(_make_stack_object(game, label="A"))
        objs = s.objects()
        objs.clear()
        assert not s.is_empty()

    def test_objects_empty_stack_returns_empty_list(self) -> None:
        """objects() on an empty stack should return an empty list."""
        s = Stack()
        assert s.objects() == []

    def test_is_empty_after_push_then_pop(self) -> None:
        """Stack should be empty again after pushing and popping one item."""
        game = _make_game()
        s = Stack()
        s.push(_make_stack_object(game))
        s.pop()
        assert s.is_empty()

    def test_objects_length_matches_push_count(self) -> None:
        """objects() should return exactly as many items as were pushed."""
        game = _make_game()
        s = Stack()
        for i in range(5):
            s.push(_make_stack_object(game, label=str(i)))
        assert len(s.objects()) == 5


# ===========================================================================
# priority_loop — empty stack (auto-pass)
# ===========================================================================
class TestPriorityLoopEmptyStack:
    """priority_loop should return immediately when both players auto-pass with empty stack."""

    def test_returns_immediately_with_empty_stack(self) -> None:
        """With empty stack and empty scripts, priority_loop returns immediately (advances phase)."""
        game = _make_game()
        priority_loop(game)  # Should not raise or loop forever
        assert game.stack.is_empty()

    def test_does_not_consume_player_choices(self) -> None:
        """With empty stack, auto-pass means choose() is never called — scripts untouched."""
        game = _make_game(p1_script=["pass"], p2_script=["pass"])
        priority_loop(game)
        # Scripts should be untouched — choose() was never called
        assert game.players[0].remaining_choices == 1
        assert game.players[1].remaining_choices == 1


# ===========================================================================
# priority_loop — stack resolution (LIFO)
# ===========================================================================
class TestPriorityLoopResolution:
    """priority_loop should resolve stack objects in LIFO order via on_resolve callbacks."""

    def test_single_object_resolved(self) -> None:
        """A single object on the stack should have its on_resolve called."""
        resolved: list[str] = []
        game = _make_game(p1_script=["pass"], p2_script=["pass"])
        game.stack.push(
            StackObject(
                source="A",
                controller=game.active_player,
                on_resolve=lambda g: resolved.append("A"),
            )
        )
        priority_loop(game)
        assert resolved == ["A"]

    def test_two_objects_lifo_order(self) -> None:
        """Two objects should resolve in LIFO order (last pushed = first resolved)."""
        resolved: list[str] = []
        game = _make_game(p1_script=["pass", "pass"], p2_script=["pass", "pass"])
        game.stack.push(
            StackObject(source="A", controller=game.active_player, on_resolve=_make_resolver("A", resolved))
        )
        game.stack.push(
            StackObject(source="B", controller=game.active_player, on_resolve=_make_resolver("B", resolved))
        )
        priority_loop(game)
        assert resolved == ["B", "A"]

    def test_three_objects_lifo_order(self) -> None:
        """Three objects should resolve in LIFO order: Z, Y, X."""
        resolved: list[str] = []
        game = _make_game(p1_script=["pass"] * 3, p2_script=["pass"] * 3)
        for label in ["X", "Y", "Z"]:
            game.stack.push(
                StackObject(
                    source=label,
                    controller=game.active_player,
                    on_resolve=_make_resolver(label, resolved),
                )
            )
        priority_loop(game)
        assert resolved == ["Z", "Y", "X"]

    def test_stack_empty_after_full_resolution(self) -> None:
        """After priority_loop completes all resolutions, the stack should be empty."""
        game = _make_game(p1_script=["pass"], p2_script=["pass"])
        game.stack.push(StackObject(source="A", controller=game.active_player))
        priority_loop(game)
        assert game.stack.is_empty()

    def test_on_resolve_receives_game_state(self) -> None:
        """on_resolve callback should receive the GameState as its argument."""
        received: list = []
        game = _make_game(p1_script=["pass"], p2_script=["pass"])
        game.stack.push(
            StackObject(
                source="test",
                controller=game.active_player,
                on_resolve=lambda g: received.append(g),
            )
        )
        priority_loop(game)
        assert len(received) == 1
        assert received[0] is game

    def test_on_resolve_side_effect_persists(self) -> None:
        """on_resolve should be able to mutate game state (e.g., change life total)."""
        game = _make_game(p1_script=["pass"], p2_script=["pass"])
        original_life = game.active_player.life

        def bolt_resolve(g):
            g.non_active_player.life -= 3

        game.stack.push(
            StackObject(source="Bolt", controller=game.active_player, on_resolve=bolt_resolve)
        )
        priority_loop(game)
        assert game.non_active_player.life == original_life - 3


# ===========================================================================
# priority_loop — priority passing with DeterministicPlayer scripts
# ===========================================================================
class TestPriorityPassing:
    """Test priority passing behavior: active player first, then non-active."""

    def test_active_player_asked_first(self) -> None:
        """Active player should be asked for a choice before non-active player."""
        asked: list[str] = []

        class TrackingPlayer(DeterministicPlayer):
            def choose(self, options, description):
                asked.append(self.name)
                return super().choose(options, description)

        p1 = TrackingPlayer("Alice", ["pass"])
        p2 = TrackingPlayer("Bob", ["pass"])
        game = GameState([p1, p2])
        game.stack.push(StackObject(source="X", controller=p1))
        priority_loop(game)
        assert asked[0] == "Alice"
        assert asked[1] == "Bob"

    def test_both_players_asked_per_resolution_round(self) -> None:
        """Each round of resolution requires both players to pass — two objects means two rounds."""
        asked_count = {"Alice": 0, "Bob": 0}

        class CountingPlayer(DeterministicPlayer):
            def choose(self, options, description):
                asked_count[self.name] += 1
                return super().choose(options, description)

        p1 = CountingPlayer("Alice", ["pass"] * 2)
        p2 = CountingPlayer("Bob", ["pass"] * 2)
        game = GameState([p1, p2])
        game.stack.push(StackObject(source="A", controller=p1))
        game.stack.push(StackObject(source="B", controller=p1))
        priority_loop(game)
        assert asked_count["Alice"] == 2
        assert asked_count["Bob"] == 2

    def test_active_player_gets_priority_again_after_resolution(self) -> None:
        """After resolving top of stack, active player should get priority again (not NAP)."""
        asked: list[str] = []

        class TrackingPlayer(DeterministicPlayer):
            def choose(self, options, description):
                asked.append(self.name)
                return super().choose(options, description)

        p1 = TrackingPlayer("Alice", ["pass"] * 2)
        p2 = TrackingPlayer("Bob", ["pass"] * 2)
        game = GameState([p1, p2])
        game.stack.push(StackObject(source="A", controller=p1))
        game.stack.push(StackObject(source="B", controller=p1))
        priority_loop(game)
        # Round 1: Alice, Bob → resolve B
        # Round 2: Alice, Bob → resolve A
        # Round 3: auto-pass (empty stack)
        # So the sequence must be Alice, Bob, Alice, Bob
        assert asked == ["Alice", "Bob", "Alice", "Bob"]


# ===========================================================================
# Mana abilities — immediate resolution (flag verification)
# ===========================================================================
class TestManaAbilities:
    """Mana abilities should resolve immediately without using the stack."""

    def test_mana_ability_flag_true(self) -> None:
        """A StackObject with is_mana_ability=True should have the flag set."""
        game = _make_game()
        mana_obj = StackObject(
            source="Llanowar Elves",
            controller=game.active_player,
            is_mana_ability=True,
        )
        assert mana_obj.is_mana_ability is True

    def test_mana_ability_on_resolve_executes(self) -> None:
        """Calling on_resolve on a mana ability should execute the callback."""
        resolved: list[str] = []
        game = _make_game()
        mana_obj = StackObject(
            source="Llanowar Elves",
            controller=game.active_player,
            on_resolve=lambda g: resolved.append("mana"),
            is_mana_ability=True,
        )
        mana_obj.on_resolve(game)
        assert resolved == ["mana"]

    def test_mana_ability_flag_default_false(self) -> None:
        """is_mana_ability should default to False for normal spells/abilities."""
        game = _make_game()
        obj = StackObject(source="x", controller=game.active_player)
        assert obj.is_mana_ability is False


# ===========================================================================
# check_state_based_actions stub
# ===========================================================================
class TestCheckStateBasedActions:
    """check_state_based_actions should be callable (stub for later implementation)."""

    def test_stub_does_not_raise(self) -> None:
        """check_state_based_actions should not raise when called on a normal game."""
        game = _make_game()
        check_state_based_actions(game)
        # Game should still be playable after SBA check
        assert not game.is_game_over

    def test_stub_returns_none(self) -> None:
        """Stub should return None."""
        game = _make_game()
        result = check_state_based_actions(game)
        assert result is None


# ===========================================================================
# GameState integration — stack initialization
# ===========================================================================
class TestGameStateStackInit:
    """Verify GameState initializes with a Stack instance."""

    def test_game_state_has_stack(self) -> None:
        """GameState.stack should be a Stack instance, not None."""
        game = _make_game()
        assert isinstance(game.stack, Stack)

    def test_game_state_stack_starts_empty(self) -> None:
        """GameState.stack should start empty."""
        game = _make_game()
        assert game.stack.is_empty()


# ===========================================================================
# Integration — run_turn with stack
# ===========================================================================
class TestRunTurnWithStack:
    """Verify run_turn works correctly with the real priority_loop from benchmarks.sos.workspace.engine.stack."""

    def test_run_turn_completes_with_empty_stack(self) -> None:
        """run_turn should complete normally with an empty stack and advance to turn 2."""
        from benchmarks.sos.workspace.engine.turn import run_turn

        game = _make_game()
        run_turn(game)
        assert game.turn_number == 2

    def test_run_turn_stack_remains_empty(self) -> None:
        """After run_turn, the stack should still be empty."""
        from benchmarks.sos.workspace.engine.turn import run_turn

        game = _make_game()
        run_turn(game)
        assert game.stack.is_empty()
