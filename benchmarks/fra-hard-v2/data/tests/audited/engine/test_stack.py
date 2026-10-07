"""Tests for engine/stack.py — Stack, StackObject, and resolving the stack.

Verifies:
- StackObject dataclass construction and defaults.
- Stack push/pop/peek/is_empty/objects methods.
- Passing with an empty stack ends the step; with objects on the stack the
  topmost resolves (last in, first out), seen through spells played at the
  table, and a response changes what the earlier spell does.
- A turn plays through to the next with the stack empty.
- A spell's copy checks its targets as it resolves (Thousand-Year Storm).
- A spell leaves the stack once, to where its cast sends it: a counterspell
  aimed at a departed spell does nothing, and only a flashback cast is exiled.
- Mana abilities resolve immediately without using the stack.
- check_state_based_actions stub is callable.
- GameState.stack is initialized as a Stack instance.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_36.card_impl import ElementalistAdept
from cards.fdn.fdn_48.card_impl import Refute
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_151.card_impl import Aetherize
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Decision, ManaType, Phase, Side, Step, Zone, card, create_game, player
from test_utils import DeterministicPlayer

from engine.game_state import GameState
from engine.stack import Stack, StackObject, check_state_based_actions
from silverquillm.table import Table, appears, copied, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)


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
# An empty stack: everyone passes and the step ends
# ===========================================================================
class TestPriorityLoopEmptyStack:
    """With nothing on the stack, all players passing in succession ends the step."""

    def test_returns_immediately_with_empty_stack(self) -> None:
        game = create_game(Side(library=[Plains]), Side(library=[Plains]), start=MAIN)
        t = Table(game)
        t.pass_(0)
        t.pass_(1, note="nothing on the stack: the step ends")
        final = t.run()
        assert final.step is Step.BEGIN_COMBAT and not final.stack


# ===========================================================================
# Resolving the stack: last in, first out
# ===========================================================================
class TestPriorityLoopResolution:
    """When all players pass in succession, the top object resolves, and the
    active player gets priority again with the rest still on the stack."""

    def test_single_object_resolved(self) -> None:
        bolt = card(BurstLightning)
        game = create_game(Side(hand=[bolt], mana={ManaType.RED: 1}), Side(), start=MAIN)
        t = Table(game)
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.run()

    def test_two_objects_lifo_order(self) -> None:
        first, second = card(BurstLightning), card(BurstLightning)
        game = create_game(Side(hand=[first, second], mana={ManaType.RED: 2}), Side(), start=MAIN)
        t = Table(game)
        t.act(0, first, choices=[player(1)], then=[moves(first, Zone.STACK)])
        t.act(0, second, choices=[player(1)], then=[moves(second, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(second, Zone.GRAVEYARD), life(1, 18)], note="the last one cast resolves first")
        t.pass_(0)
        t.pass_(1, then=[moves(first, Zone.GRAVEYARD), life(1, 16)])
        t.run()

    def test_three_objects_lifo_order(self) -> None:
        bolts = [card(BurstLightning) for _ in range(3)]
        game = create_game(Side(hand=bolts, mana={ManaType.RED: 3}), Side(), start=MAIN)
        t = Table(game)
        for bolt in bolts:
            t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
        for total, bolt in zip((18, 16, 14), reversed(bolts)):
            t.pass_(0)
            t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, total)], note="the topmost resolves")
        t.run()

    def test_stack_empty_after_full_resolution(self) -> None:
        bolt = card(BurstLightning)
        game = create_game(Side(hand=[bolt], library=[Plains], mana={ManaType.RED: 1}), Side(), start=MAIN)
        t = Table(game)
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.pass_(0)
        t.pass_(1, note="the stack is empty, so passing ends the step")
        final = t.run()
        assert final.step is Step.BEGIN_COMBAT

    def test_on_resolve_receives_game_state(self) -> None:
        bolt, lions = card(BurstLightning), card(SavannahLions)
        game = create_game(Side(hand=[bolt], mana={ManaType.RED: 1}), Side(battlefield=[lions]), start=MAIN)
        t = Table(game)
        t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)], note="the spell acts on the game it resolves in")
        t.run()

    def test_on_resolve_side_effect_persists(self) -> None:
        bolt = card(BurstLightning)
        game = create_game(Side(hand=[bolt], library=[Plains], mana={ManaType.RED: 1}), Side(), start=MAIN)
        t = Table(game)
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.pass_to(Step.END, 0)
        final = t.run()
        assert final.players[1].life == 18


# ===========================================================================
# Responses resolve before what they respond to
# ===========================================================================
class TestPriorityMultiObjectResolution:
    """A response, put on the stack later, resolves first and can change what
    the earlier object does."""

    def test_two_objects_resolve_top_then_bottom(self) -> None:
        bolt, growth, lions = card(BurstLightning), card(GiantGrowth), card(SavannahLions)
        game = create_game(
            Side(hand=[bolt], mana={ManaType.RED: 1}),
            Side(hand=[growth], battlefield=[lions], mana={ManaType.GREEN: 1}),
            start=MAIN,
        )
        t = Table(game)
        t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.act(1, growth, choices=[lions], then=[moves(growth, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(growth, Zone.GRAVEYARD)], note="Giant Growth, on top, resolves first")
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD)], note="the 5/4 Lions survives 2 damage")
        t.run()

    def test_full_stack_drains_in_lifo_order(self) -> None:
        first, growth, second, lions = card(BurstLightning), card(GiantGrowth), card(BurstLightning), card(SavannahLions)
        game = create_game(
            Side(hand=[first, second], mana={ManaType.RED: 2}),
            Side(hand=[growth], battlefield=[lions], mana={ManaType.GREEN: 1}),
            start=MAIN,
        )
        t = Table(game)
        t.act(0, first, choices=[lions], then=[moves(first, Zone.STACK)])
        t.pass_(0)
        t.act(1, growth, choices=[lions], then=[moves(growth, Zone.STACK)])
        t.pass_(1)
        t.act(0, second, choices=[lions], then=[moves(second, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(second, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)], note="the last Burst Lightning kills the 2/1 first")
        t.pass_(0)
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)], note="Giant Growth's target is gone")
        t.pass_(0)
        t.pass_(1, then=[moves(first, Zone.GRAVEYARD)], note="and so is the first Burst Lightning's")
        final = t.run()
        assert not final.stack


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
# Playing through a turn
# ===========================================================================
class TestRunTurnWithStack:
    """A turn plays through to the next player's turn, with the stack empty."""

    def test_run_turn_completes_with_empty_stack(self) -> None:
        game = create_game(Side(), Side(), start=(Step.UPKEEP, 0))
        t = Table(game)
        t.pass_to(Step.UPKEEP, 1)
        final = t.run()
        assert (final.active, final.step) == (1, Step.UPKEEP) and not final.stack

    def test_run_turn_stack_remains_empty(self) -> None:
        bolt = card(BurstLightning)
        game = create_game(Side(hand=[bolt], mana={ManaType.RED: 1}), Side(), start=MAIN)
        t = Table(game)
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.pass_to(Step.UPKEEP, 1)
        final = t.run()
        assert final.active == 1 and not final.stack


def _storm_copies_second_bolt(t, first, second, target, *, new_target=None):
    """Player 0, with Thousand-Year Storm, casts ``first`` at player 1 and lets
    it resolve, then casts ``second`` at ``target``: Storm copies it once,
    keeping its target or, with ``new_target``, choosing that one."""
    t.act(0, first, choices=[player(1)], then=[moves(first, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ThousandYearStormAbility1)])
    t.pass_(0)
    t.pass_(1, then=[moves(first, Zone.GRAVEYARD), life(1, 18)])
    _second_bolt_copied(t, second, target, new_target, opponent=1)


def _second_bolt_copied(t, second, target, new_target, *, opponent):
    t.act(0, second, choices=[target], then=[moves(second, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
    retarget = [Decision.no()] if new_target is None else [Decision.yes(), new_target]
    t.pass_(0, choices=retarget)
    t.pass_(opponent, then=[off_stack(ThousandYearStormAbility1), copied(BurstLightning, 0)], note="the second spell is copied")


def _attacking_adept_bounced_and_recast(t, first, second, adept, aetherize, mountains, islands, *, new_target=None, target=None):
    """On player 1's turn the Elementalist Adept attacks; player 0 copies a
    Burst Lightning aimed at it (or at ``target``, the copy choosing the
    Adept), and player 1 answers with Aetherize, returning the Adept to hand,
    and casts it again: a new object."""
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, adept, then=[taps(adept)])
    t.pass_(1)
    t.act(0, mountains[0], then=[taps(mountains[0])])
    t.act(0, first, choices=[player(1)], then=[moves(first, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ThousandYearStormAbility1)])
    t.pass_(1)
    t.pass_(0, then=[moves(first, Zone.GRAVEYARD), life(1, 18)])
    t.pass_(1)
    t.act(0, mountains[1], then=[taps(mountains[1])])
    _second_bolt_copied(t, second, target or adept, new_target, opponent=1)
    for island in islands[:4]:
        t.act(1, island, then=[taps(island)])
    t.act(1, aetherize, then=[moves(aetherize, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(aetherize, Zone.GRAVEYARD), moves(adept, Zone.HAND)])
    for island in islands[4:]:
        t.act(1, island, then=[taps(island)])
    t.act(1, adept, then=[moves(adept, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(adept, Zone.BATTLEFIELD)], note="the Elementalist Adept is back as a new object")


def _combat_board(target=None):
    first, second, adept, aetherize = card(BurstLightning), card(BurstLightning), card(ElementalistAdept), card(Aetherize)
    mountains = [card(Mountain), card(Mountain)]
    islands = [card(Island) for _ in range(6)]
    game = create_game(
        Side(hand=[first, second], battlefield=[ThousandYearStorm, *mountains]),
        Side(hand=[aetherize], battlefield=[adept, *islands, *([target] if target else [])], library=[Plains]),
        start=(Step.BEGIN_COMBAT, 1),
    )
    return game, first, second, adept, aetherize, mountains, islands


class TestCopySpellStintRevalidation:
    """A copy of a spell checks its targets as it resolves, like the spell:
    a copy keeping the original's target, or choosing a new one, affects it
    if it is still there, and does nothing to a creature that left the
    battlefield and came back, which is a new object (CR 400.7).

    Thousand-Year Storm copies the second instant a player casts in a turn,
    and Aetherize returns an attacking creature to hand, to be cast again."""

    def test_retained_targets_copy_marks_when_target_stays(self):
        first, second, scourge = card(BurstLightning), card(BurstLightning), card(BrazenScourge)
        game = create_game(
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={ManaType.RED: 2}),
            Side(battlefield=[scourge]),
            start=MAIN,
        )
        t = Table(game)
        _storm_copies_second_bolt(t, first, second, scourge)
        t.pass_(0)
        t.pass_(1, then=[off_stack(BurstLightning)], note="the copy deals 2 to Brazen Scourge")
        t.pass_(0)
        t.pass_(1, then=[moves(second, Zone.GRAVEYARD), moves(scourge, Zone.GRAVEYARD)], note="the original's 2 more destroy the 3/3")
        t.run()

    def test_retained_targets_copy_rejects_leave_and_return(self):
        game, first, second, adept, aetherize, mountains, islands = _combat_board()
        t = Table(game)
        _attacking_adept_bounced_and_recast(t, first, second, adept, aetherize, mountains, islands)
        t.pass_(1)
        t.pass_(0, then=[off_stack(BurstLightning)], note="the copy's target left the battlefield: it does nothing")
        t.pass_(1)
        t.pass_(0, then=[moves(second, Zone.GRAVEYARD)])
        t.run()

    def test_new_targets_copy_marks_when_target_stays(self):
        first, second, scourge, lions = card(BurstLightning), card(BurstLightning), card(BrazenScourge), card(SavannahLions)
        game = create_game(
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={ManaType.RED: 2}),
            Side(battlefield=[scourge, lions]),
            start=MAIN,
        )
        t = Table(game)
        _storm_copies_second_bolt(t, first, second, scourge, new_target=lions)
        t.pass_(0)
        t.pass_(1, then=[off_stack(BurstLightning), moves(lions, Zone.GRAVEYARD)], note="the copy hits its new target")
        t.pass_(0)
        t.pass_(1, then=[moves(second, Zone.GRAVEYARD)], note="Brazen Scourge takes only the original's 2")
        t.run()

    def test_new_targets_copy_rejects_leave_and_return(self):
        scourge = card(BrazenScourge)
        game, first, second, adept, aetherize, mountains, islands = _combat_board(scourge)
        t = Table(game)
        _attacking_adept_bounced_and_recast(
            t, first, second, adept, aetherize, mountains, islands, target=scourge, new_target=adept
        )
        t.pass_(1)
        t.pass_(0, then=[off_stack(BurstLightning)], note="the copy's new target left the battlefield: it does nothing")
        t.pass_(1)
        t.pass_(0, then=[moves(second, Zone.GRAVEYARD)], note="Brazen Scourge takes the original's 2 and survives")
        t.run()


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
        from test_utils import create_game

        from engine.stack import move_spell_off_stack
        from engine.types import Zone

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
        from test_utils import create_game

        from engine.stack import move_spell_off_stack
        from engine.types import Zone

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
        from test_utils import create_game

        from engine.casting import CastMode
        from engine.stack import move_spell_off_stack
        from engine.types import Zone

        game = create_game()
        p = game.players[0]
        card = self._instant(p, flashback=True)
        game.get_graveyard(p).add(card)
        so = self._cast(game, p, card, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)

        assert move_spell_off_stack(game, so) is True
        assert game.get_exile(p).contains(card)
        assert not game.get_graveyard(p).contains(card)

    def _countered_by_the_second_counterspell(self, t, think, refute, offer):
        """Player 1 answers Think Twice with Refute, then An Offer You Can't
        Refuse on top; the Offer counters it first (two Treasures for its
        controller), leaving Refute aimed at a spell that is gone."""
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.act(1, refute, choices=[think], then=[moves(refute, Zone.STACK)])
        t.act(1, offer, choices=[think], then=[moves(offer, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(think, Zone.GRAVEYARD), appears(0), appears(0)])

    def test_counter_fizzles_after_departure(self):
        """A counterspell whose spell already left the stack does nothing:
        the spell is not moved again, and Refute neither draws nor discards."""
        think, refute, offer = card(ThinkTwice), card(Refute), card(AnOfferYouCantRefuse)
        game = create_game(
            Side(hand=[think], library=[Plains], mana={ManaType.BLUE: 2}),
            Side(hand=[refute, offer], library=[Plains], mana={ManaType.BLUE: 4}),
            start=MAIN,
        )
        t = Table(game)
        self._countered_by_the_second_counterspell(t, think, refute, offer)
        t.pass_(0)
        t.pass_(1, then=[moves(refute, Zone.GRAVEYARD)], note="Refute's target is gone: it does nothing")
        t.run()

    def test_fizzled_counter_never_moves_recast_card(self):
        """The countered card is cast again with flashback while Refute still
        aims at its first cast: Refute does nothing, and the card goes where
        its second cast sends it."""
        think, refute, offer, drawn = card(ThinkTwice), card(Refute), card(AnOfferYouCantRefuse), card(Plains)
        game = create_game(
            Side(hand=[think], library=[drawn], mana={ManaType.BLUE: 5}),
            Side(hand=[refute, offer], mana={ManaType.BLUE: 4}),
            start=MAIN,
        )
        t = Table(game)
        self._countered_by_the_second_counterspell(t, think, refute, offer)
        t.act(0, think, then=[moves(think, Zone.STACK)], note="flashback: Think Twice is cast again")
        t.pass_(0)
        t.pass_(1, then=[moves(think, Zone.EXILE), moves(drawn, Zone.HAND)])
        t.pass_(0)
        t.pass_(1, then=[moves(refute, Zone.GRAVEYARD)], note="Refute does nothing and leaves Think Twice in exile")
        t.run()


    def test_countering_copy_departs_without_card_move(self):
        """Countering a spell COPY removes its StackObject; a copy's card
        object occupies no stack zone (copies cease to exist, rule 707.10a),
        so no card moves and the original cast is untouched."""
        from test_utils import create_game

        from engine.stack import copy_spell, move_spell_off_stack
        from engine.types import Zone

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
        """A copy of a flashback cast is not cast with flashback: it resolves
        without exiling the card, which stays on the stack until its own
        cast resolves and is exiled."""
        bolt, think, one, two = card(BurstLightning), card(ThinkTwice), card(Plains), card(Plains)
        game = create_game(
            Side(
                hand=[bolt],
                graveyard=[think],
                battlefield=[ThousandYearStorm],
                library=[one, two],
                mana={ManaType.RED: 1, ManaType.BLUE: 3},
            ),
            Side(),
            start=MAIN,
        )
        t = Table(game)
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ThousandYearStormAbility1)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.act(0, think, then=[moves(think, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)], note="flashback")
        t.pass_(0)
        t.pass_(1, then=[off_stack(ThousandYearStormAbility1), copied(ThinkTwice, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ThinkTwice), moves(one, Zone.HAND)], note="the copy resolves; Think Twice stays on the stack")
        t.pass_(0)
        t.pass_(1, then=[moves(think, Zone.EXILE), moves(two, Zone.HAND)])
        t.run()

    def test_disposition_is_per_cast_occurrence(self):
        """Exile belongs to the flashback cast, not the card: cast from hand
        it goes to the graveyard, and cast from there with flashback the same
        card is exiled."""
        think, one, two = card(ThinkTwice), card(Plains), card(Plains)
        game = create_game(Side(hand=[think], library=[one, two], mana={ManaType.BLUE: 5}), Side(), start=MAIN)
        t = Table(game)
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(think, Zone.GRAVEYARD), moves(one, Zone.HAND)], note="cast from hand: it goes to the graveyard")
        t.act(0, think, then=[moves(think, Zone.STACK)], note="flashback")
        t.pass_(0)
        t.pass_(1, then=[moves(think, Zone.EXILE), moves(two, Zone.HAND)], note="the flashback cast is exiled")
        t.run()
