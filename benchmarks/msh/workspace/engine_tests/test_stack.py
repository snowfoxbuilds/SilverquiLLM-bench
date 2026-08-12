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

from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer
from engine.stack import Stack, StackObject, check_state_based_actions, priority_loop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_game() -> GameState:
    """Create a 2-player GameState with intent-based DeterministicPlayers."""
    p1 = DeterministicPlayer("Alice", life=20)
    p2 = DeterministicPlayer("Bob", life=20)
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
        """With an empty stack, priority_loop returns immediately (advances phase)."""
        game = _make_game()
        priority_loop(game)  # Should not raise or loop forever
        assert game.stack.is_empty()


# ===========================================================================
# priority_loop — stack resolution (LIFO)
# ===========================================================================
class TestPriorityLoopResolution:
    """priority_loop should resolve stack objects in LIFO order via on_resolve callbacks."""

    def test_single_object_resolved(self) -> None:
        """A single object on the stack should have its on_resolve called."""
        resolved: list[str] = []
        game = _make_game()
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
        game = _make_game()
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
        game = _make_game()
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
        game = _make_game()
        game.stack.push(StackObject(source="A", controller=game.active_player))
        priority_loop(game)
        assert game.stack.is_empty()

    def test_on_resolve_receives_game_state(self) -> None:
        """on_resolve callback should receive the GameState as its argument."""
        received: list = []
        game = _make_game()
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
        game = _make_game()
        original_life = game.active_player.life

        def bolt_resolve(g):
            g.non_active_player.life -= 3

        game.stack.push(
            StackObject(source="Bolt", controller=game.active_player, on_resolve=bolt_resolve)
        )
        priority_loop(game)
        assert game.non_active_player.life == original_life - 3


# ===========================================================================
# priority_loop — multi-object resolution ordering
# ===========================================================================
class TestPriorityMultiObjectResolution:
    """Multiple stacked objects resolve top-down across resolution rounds.

    Priority is now directive-driven (``priority_loop`` auto-passes; the player
    is never queried for a priority action), so these verify resolution order
    rather than the deleted priority-choice scripting.
    """

    def test_two_objects_resolve_top_then_bottom(self) -> None:
        """Two stacked objects resolve in LIFO order: top (B) then bottom (A)."""
        resolved: list[str] = []
        game = _make_game()
        game.stack.push(
            StackObject(source="A", controller=game.active_player, on_resolve=_make_resolver("A", resolved))
        )
        game.stack.push(
            StackObject(source="B", controller=game.active_player, on_resolve=_make_resolver("B", resolved))
        )
        priority_loop(game)
        assert resolved == ["B", "A"]
        assert game.stack.is_empty()

    def test_full_stack_drains_in_lifo_order(self) -> None:
        """priority_loop resolves every stacked object, top-down, until empty."""
        resolved: list[str] = []
        game = _make_game()
        for label in ["A", "B", "C"]:
            game.stack.push(
                StackObject(source=label, controller=game.active_player, on_resolve=_make_resolver(label, resolved))
            )
        priority_loop(game)
        assert resolved == ["C", "B", "A"]
        assert game.stack.is_empty()


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
    """Verify run_turn works correctly with the real priority_loop from engine.stack."""

    def test_run_turn_completes_with_empty_stack(self) -> None:
        """run_turn should complete normally with an empty stack and advance to turn 2."""
        from engine.turn import run_turn

        game = _make_game()
        run_turn(game)
        assert game.turn_number == 2

    def test_run_turn_stack_remains_empty(self) -> None:
        """After run_turn, the stack should still be empty."""
        from engine.turn import run_turn

        game = _make_game()
        run_turn(game)
        assert game.stack.is_empty()


class TestCopySpellStintRevalidation:
    """copy_spell carries an ActivationContext so a copied spell stint-revalidates
    its targets at resolution — retained targets inherit the original's stint
    ids; newly chosen targets capture their current stints; either is rejected on
    a leave-and-return."""

    def _mark_spell(self, owner):
        from engine.card import Instant

        class _MarkCreature(Instant):
            def on_resolve(self, game):
                chosen = getattr(self, "chosen_targets", None) or []
                target = chosen[0] if chosen else None
                if target is not None:
                    target._marked = True

        return _MarkCreature(name="Mark Copy", owner=owner, controller=owner)

    def _board(self):
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        other = Creature(name="Other", base_power=2, base_toughness=2, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[bear, other])
        return game, p1, p2, bear, other

    def _original(self, game, p1, spell, targets):
        from engine.stack import StackObject, capture_activation_context
        return StackObject(
            source=spell,
            controller=p1,
            targets=list(targets),
            activation_context=capture_activation_context(game, spell, p1, list(targets)),
        )

    def test_retained_targets_copy_marks_when_target_stays(self):
        from engine.stack import copy_spell, resolve_top_of_stack
        game, p1, p2, bear, other = self._board()
        spell = self._mark_spell(p1)
        original = self._original(game, p1, spell, [bear])
        game.stack.push(copy_spell(game, original, p1))   # retain targets
        resolve_top_of_stack(game)
        assert getattr(bear, "_marked", False) is True

    def test_retained_targets_copy_rejects_leave_and_return(self):
        from engine.stack import copy_spell, resolve_top_of_stack
        from engine.types import Zone
        from engine.zones import move_to_zone
        game, p1, p2, bear, other = self._board()
        spell = self._mark_spell(p1)
        original = self._original(game, p1, spell, [bear])
        game.stack.push(copy_spell(game, original, p1))   # inherits bear's stint id
        move_to_zone(game, bear, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, bear, Zone.EXILE, Zone.BATTLEFIELD)  # new stint
        resolve_top_of_stack(game)
        assert getattr(bear, "_marked", False) is False   # rejected by inherited stint

    def test_new_targets_copy_marks_when_target_stays(self):
        from engine.stack import copy_spell, resolve_top_of_stack
        game, p1, p2, bear, other = self._board()
        spell = self._mark_spell(p1)
        original = self._original(game, p1, spell, [bear])
        # Copy chooses a NEW target (other) — its current stint is captured.
        game.stack.push(copy_spell(game, original, p1, new_targets=[other]))
        resolve_top_of_stack(game)
        assert getattr(other, "_marked", False) is True
        assert getattr(bear, "_marked", False) is False   # original target untouched

    def test_new_targets_copy_rejects_leave_and_return(self):
        from engine.stack import copy_spell, resolve_top_of_stack
        from engine.types import Zone
        from engine.zones import move_to_zone
        game, p1, p2, bear, other = self._board()
        spell = self._mark_spell(p1)
        original = self._original(game, p1, spell, [bear])
        game.stack.push(copy_spell(game, original, p1, new_targets=[other]))
        move_to_zone(game, other, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, other, Zone.EXILE, Zone.BATTLEFIELD)  # new stint
        resolve_top_of_stack(game)
        assert getattr(other, "_marked", False) is False  # rejected by captured stint


class TestMoveSpellOffStack:
    """move_spell_off_stack is the single primitive through which every spell
    leaves the stack. Countering (default) removes exactly the given
    StackObject and puts an ordinary spell in its owner's graveyard; the cast's
    departure replacement (flashback -> exile, rule 702.34a) is honoured for
    resolution and countering alike; a card is never moved twice; and a
    fizzled counter never moves a re-cast card."""

    def _instant(self, owner, name="Zap", *, flashback=False):
        from engine.card import Instant
        from engine.types import ManaCost

        card = Instant(name=name, mana_cost=ManaCost.parse("{U}"), owner=owner)
        card.controller = owner
        if flashback:
            card.flashback_cost = ManaCost.parse("{2}{U}")
        return card

    def _cast(self, game, player, card, from_zone, mode=None):
        """Free-cast *card* and return its StackObject (the cast helper's own
        return value — the occurrence identity of this one cast)."""
        from engine.casting import cast_spell_free

        if mode is None:
            so = cast_spell_free(game, player, card, from_zone)
        else:
            so = cast_spell_free(game, player, card, from_zone, mode=mode)
        assert so is game.stack.peek()  # the just-pushed occurrence
        assert so.source is card
        return so

    def test_countered_ordinary_spell_to_owner_graveyard(self):
        from engine.stack import move_spell_off_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p = game.players[0]
        card = self._instant(p)
        game.get_hand(p).add(card)
        so = self._cast(game, p, card, Zone.HAND)

        assert move_spell_off_stack(game, so) is True
        assert game.stack.is_empty()
        assert game.get_graveyard(p).contains(card)
        assert not p.zones[Zone.STACK].contains(card)

    def test_countered_spell_owned_by_other_player_goes_to_owner(self):
        """Owner/controller split: the countered card goes to its OWNER's
        graveyard even when another player cast (controls) it."""
        from engine.stack import move_spell_off_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p1, p2 = game.players
        card = self._instant(p2)          # owned by p2
        game.get_hand(p1).add(card)       # but cast out of p1's hand
        so = self._cast(game, p1, card, Zone.HAND)
        assert so.controller is p1

        assert move_spell_off_stack(game, so) is True
        assert game.get_graveyard(p2).contains(card)
        assert not game.get_graveyard(p1).contains(card)

    def test_countered_flashback_cast_exiled(self):
        """A spell cast via flashback is exiled when countered, not sent to
        the graveyard (rule 702.34a: any time it would leave the stack)."""
        from engine.casting import CastMode
        from engine.stack import move_spell_off_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p = game.players[0]
        card = self._instant(p, flashback=True)
        game.get_graveyard(p).add(card)
        so = self._cast(game, p, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)

        assert move_spell_off_stack(game, so) is True
        assert game.get_exile(p).contains(card)
        assert not game.get_graveyard(p).contains(card)

    def test_counter_fizzles_after_departure(self):
        """A StackObject that already left the stack (it resolved) is not
        processed again: no removal, no card move, returns False."""
        from engine.stack import move_spell_off_stack, resolve_top_of_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p = game.players[0]
        card = self._instant(p)
        game.get_hand(p).add(card)
        so = self._cast(game, p, card, Zone.HAND)
        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)

        assert move_spell_off_stack(game, so) is False
        # Exactly one graveyard occupancy, nothing exiled.
        assert sum(1 for o in game.get_graveyard(p).get_all() if o is card) == 1
        assert not game.get_exile(p).contains(card)

    def test_fizzled_counter_never_moves_recast_card(self):
        """After the targeted occurrence resolved and the same card was re-cast,
        countering the OLD occurrence moves nothing: the card's stack-zone
        presence belongs to the new cast."""
        from engine.stack import move_spell_off_stack, resolve_top_of_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p = game.players[0]
        card = self._instant(p)
        game.get_hand(p).add(card)
        so_first = self._cast(game, p, card, Zone.HAND)
        resolve_top_of_stack(game)                       # -> graveyard
        so_second = self._cast(game, p, card, Zone.GRAVEYARD)  # re-cast
        assert p.zones[Zone.STACK].contains(card)

        assert move_spell_off_stack(game, so_first) is False
        # The new occurrence is untouched: still on the stack, card still in
        # the stack zone.
        assert any(item is so_second for item in game.stack._items)
        assert p.zones[Zone.STACK].contains(card)
        assert not game.get_graveyard(p).contains(card)

        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)

    def test_resolution_does_not_move_twice_when_on_resolve_moved(self):
        """resolving=True duplicate-move guard: an on_resolve that already
        moved its card out of the stack zone leaves nothing for the departure
        primitive to move."""
        from engine.card import Instant
        from engine.stack import resolve_top_of_stack
        from engine.types import ManaCost, Zone
        from test_utils import create_game

        class _SelfBouncer(Instant):
            def on_resolve(self, game):
                from engine.zones import move_to_zone

                move_to_zone(game, self, Zone.STACK, Zone.HAND)

        game = create_game()
        p = game.players[0]
        card = _SelfBouncer(name="Boomerang Trick", mana_cost=ManaCost.parse("{U}"), owner=p)
        card.controller = p
        game.get_hand(p).add(card)
        self._cast(game, p, card, Zone.HAND)

        resolve_top_of_stack(game)
        assert sum(1 for o in game.get_hand(p).get_all() if o is card) == 1
        assert not game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)

    def test_countering_copy_departs_without_card_move(self):
        """Countering a spell COPY removes its StackObject; a copy's card
        object occupies no stack zone (copies cease to exist, rule 707.10a),
        so no card moves and the original cast is untouched."""
        from engine.stack import copy_spell, move_spell_off_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p = game.players[0]
        card = self._instant(p)
        game.get_hand(p).add(card)
        so = self._cast(game, p, card, Zone.HAND)
        copy_obj = copy_spell(game, so, p)
        game.stack.push(copy_obj)

        assert move_spell_off_stack(game, copy_obj) is True
        assert not any(item is copy_obj for item in game.stack._items)
        # The original occurrence is untouched.
        assert any(item is so for item in game.stack._items)
        assert p.zones[Zone.STACK].contains(card)
        assert not game.get_graveyard(p).contains(card)
        assert not game.get_graveyard(p).contains(copy_obj.source)

    def test_copy_of_flashback_cast_is_unaffected(self):
        """Disposition is per cast occurrence: a COPY of a flashback cast is
        not itself a flashback cast — it carries no departure_zone, and
        resolving it never moves (or exiles) the original card."""
        from engine.casting import CastMode
        from engine.stack import copy_spell, resolve_top_of_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p = game.players[0]
        card = self._instant(p, flashback=True)
        game.get_graveyard(p).add(card)
        so = self._cast(game, p, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)
        copy_obj = copy_spell(game, so, p)
        game.stack.push(copy_obj)
        assert copy_obj.departure_zone is None

        resolve_top_of_stack(game)                 # resolves the copy
        assert p.zones[Zone.STACK].contains(card)  # original still cast
        assert not game.get_exile(p).contains(card)

        resolve_top_of_stack(game)                 # resolves the original
        assert game.get_exile(p).contains(card)    # flashback exile intact

    def test_disposition_is_per_cast_occurrence(self):
        """The exile override belongs to the flashback OCCURRENCE, never the
        card: after a flashback cast is countered into exile, a later NORMAL
        graveyard cast of the same card keeps the graveyard default."""
        from engine.casting import CastMode
        from engine.stack import move_spell_off_stack, resolve_top_of_stack
        from engine.types import Zone
        from test_utils import create_game

        game = create_game()
        p = game.players[0]
        card = self._instant(p, flashback=True)
        game.get_graveyard(p).add(card)
        so_flash = self._cast(game, p, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)
        assert move_spell_off_stack(game, so_flash) is True
        assert game.get_exile(p).contains(card)

        # Test scaffolding: put the card back in the graveyard.
        game.get_exile(p).remove(card)
        game.get_graveyard(p).add(card)

        so_normal = self._cast(game, p, card, Zone.GRAVEYARD)
        assert so_normal.departure_zone is None
        resolve_top_of_stack(game)
        assert game.get_graveyard(p).contains(card)
        assert not game.get_exile(p).contains(card)
