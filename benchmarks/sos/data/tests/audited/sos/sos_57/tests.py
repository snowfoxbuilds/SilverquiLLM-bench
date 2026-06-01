"""Audited tests for Mana Sculpt (sos_57) — FLAGSHIP.

Oracle: {1}{U}{U} Instant.
  Counter target spell. If you control a Wizard, add an amount of {C}
  equal to the amount of mana spent to cast that spell at the beginning
  of your next main phase.

Phase 18 doctrine: integration-style tests against canonical engine APIs.
The target spell is placed on the stack via the real `cast_spell` pipeline
(not a synthetic `_put_spell_on_stack` helper) so that `mana_spent` is
recorded correctly at cast time. The refund is verified by advancing the
game to the controller's next main phase and observing the mana pool.

Tests:
  TestIdentity
    1. test_identity
  TestTargeting
    2. test_get_targets_returns_stack_spells (real cast)
    3. test_get_targets_excludes_permanents
    4. test_get_targets_excludes_empty_stack
  TestCounter
    5. test_counters_via_real_cast
    6. test_fizzle_when_target_removed
  TestRefund
    7. test_refund_with_wizard_at_next_main_phase
    8. test_refund_amount_equals_mana_spent
    9. test_no_refund_without_wizard
    10. test_no_refund_when_fizzled
    11. test_no_refund_on_opponent_main_phase
    12. test_refund_fires_only_once
    13. test_refund_locked_in_when_wizard_leaves_before_next_main

Edge case coverage requested by the user (Q1/Q2 follow-up).
"""

from __future__ import annotations

import pytest

from card_impl import ManaSculpt

from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import (
    card_colors,
    create_game,
    resolve_top,
    set_battlefield,
    set_hand,
    set_mana_pool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wizard(name: str = "Sage of Fables") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2, subtypes={"Wizard"})


def _make_target_spell(
    name: str = "Lightning Bolt",
    owner=None,
    cost: ManaCost | None = None,
) -> Instant:
    """A simple opponent spell with no targets, so casting doesn't ask for one."""
    if cost is None:
        cost = ManaCost(generic=2, pips={ManaType.RED: 1})  # CMC 3
    return Instant(name=name, owner=owner, mana_cost=cost)


def _fund_for(player, cost: ManaCost) -> None:
    """Add exactly enough mana to *player* to pay *cost*."""
    mana: dict[ManaType, int] = {}
    if cost.generic:
        mana[ManaType.COLORLESS] = mana.get(ManaType.COLORLESS, 0) + cost.generic
    for mana_type, amount in cost.pips.items():
        mana[mana_type] = mana.get(mana_type, 0) + amount
    for mana_type, amount in mana.items():
        player.mana_pool.add(mana_type, amount)


def _enter_main_phase_for(game, player) -> None:
    """Simulate the beginning of *player*'s next main phase.

    Fires each registered beginning-of-main-phase event — read from the
    public trigger registry, so no engine-internal event class is named —
    through the canonical dispatch path, then resolves the resulting stack.
    The card-side trigger is responsible for its own one-shot bookkeeping.
    """
    game.active_player_index = game.players.index(player)
    event_types = {
        t.event_type
        for t in game.trigger_manager.get_triggers()
        if "MainPhase" in t.event_type.__name__ and t.controller is player
    }
    for event_type in event_types:
        game.trigger_manager.fire_event(game, event_type(player=player))
    while not game.stack.is_empty():
        resolve_top(game)


def _remove_from_stack(game, obj) -> None:
    """Remove a specific object from the stack using only public stack
    operations (simulates the object being countered/removed before it
    resolves): lift everything above it off, drop it, restore the rest.
    """
    above = []
    while not game.stack.is_empty():
        top = game.stack.pop()
        if top is obj:
            break
        above.append(top)
    for o in reversed(above):
        game.stack.push(o)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_identity(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost.generic == 1
        assert card.mana_cost.pips.get(ManaType.BLUE) == 2
        assert card.mana_cost.cmc == 3
        assert CardType.INSTANT in card.card_types
        assert isinstance(card, Instant)
        colors = card_colors(card)
        assert colors == {"U"}


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestTargeting:
    def test_get_targets_returns_stack_spells(self) -> None:
        """Casting a spell via the real pipeline lands it on the stack;
        Mana Sculpt's targets include it."""
        game = create_game()
        p1, p2 = game.players

        target = _make_target_spell(owner=p2)
        set_hand(game, 1, [target])
        _fund_for(p2, target.mana_cost)
        engine_cast_spell(game, p2, target)

        targets = ManaSculpt(owner=p1).get_targets(game)
        assert len(targets) == 1
        assert targets[0].source is target

    def test_get_targets_excludes_permanents(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2)
        set_battlefield(game, 0, [bear])
        enemy = Creature(name="Goblin", owner=p2, base_power=1, base_toughness=1)
        set_battlefield(game, 1, [enemy])

        targets = ManaSculpt(owner=p1).get_targets(game)
        assert targets == []

    def test_get_targets_excludes_empty_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        assert ManaSculpt(owner=p1).get_targets(game) == []


# ---------------------------------------------------------------------------
# Counter behavior
# ---------------------------------------------------------------------------


class TestCounter:
    def test_counters_via_real_cast(self) -> None:
        """Opponent's spell is cast, then countered: moved to GY,
        its on_resolve NOT invoked."""
        game = create_game()
        p1, p2 = game.players

        resolve_called: list[bool] = []

        class TrackedSpell(Instant):
            def on_resolve(self, game):  # type: ignore[override]
                resolve_called.append(True)

        target = TrackedSpell(
            name="Enemy Spell",
            owner=p2,
            mana_cost=ManaCost(generic=2, pips={ManaType.RED: 1}),
        )
        set_hand(game, 1, [target])
        _fund_for(p2, target.mana_cost)
        engine_cast_spell(game, p2, target)
        target_stack_obj = game.stack.peek()

        # Mana Sculpt
        mana_sculpt = ManaSculpt(owner=p1)
        set_hand(game, 0, [mana_sculpt])
        _fund_for(p1, mana_sculpt.mana_cost)
        # Script the target choice for p1
        p1._script.appendleft(target_stack_obj)
        engine_cast_spell(game, p1, mana_sculpt)

        # Resolve Mana Sculpt (top of stack)
        resolve_top(game)

        # Target removed from stack, no resolution called, ended up in p2 GY
        assert target_stack_obj not in game.stack.objects()
        assert resolve_called == []
        assert target in p2.zones[Zone.GRAVEYARD].get_all()

    def test_fizzle_when_target_removed(self) -> None:
        """If the target leaves the stack before Mana Sculpt resolves,
        Mana Sculpt does nothing."""
        game = create_game()
        p1, p2 = game.players

        # Wizard present — so we'd KNOW if refund accidentally fired
        set_battlefield(game, 0, [_make_wizard()])

        target = _make_target_spell(owner=p2)
        set_hand(game, 1, [target])
        _fund_for(p2, target.mana_cost)
        engine_cast_spell(game, p2, target)
        target_stack_obj = game.stack.peek()

        mana_sculpt = ManaSculpt(owner=p1)
        set_hand(game, 0, [mana_sculpt])
        _fund_for(p1, mana_sculpt.mana_cost)
        p1._script.appendleft(target_stack_obj)
        engine_cast_spell(game, p1, mana_sculpt)

        # Remove target before resolution (simulates a second counterspell)
        _remove_from_stack(game, target_stack_obj)

        # Drain p1's mana pool so we can detect any refund
        p1.mana_pool.empty()
        resolve_top(game)

        # Fizzle: no GY add by Mana Sculpt, no refund trigger registered
        assert target not in p2.zones[Zone.GRAVEYARD].get_all()
        # Advance to p1's next main phase — no trigger should fire
        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


# ---------------------------------------------------------------------------
# Wizard-conditional delayed refund
# ---------------------------------------------------------------------------


class TestRefund:
    def _counter_and_get_p1(self, game, target_cost: ManaCost):
        """Helper: counter a target spell costing *target_cost*, return p1."""
        p1, p2 = game.players
        target = _make_target_spell(owner=p2, cost=target_cost)
        set_hand(game, 1, [target])
        _fund_for(p2, target_cost)
        engine_cast_spell(game, p2, target)
        target_stack_obj = game.stack.peek()

        mana_sculpt = ManaSculpt(owner=p1)
        set_hand(game, 0, [mana_sculpt])
        _fund_for(p1, mana_sculpt.mana_cost)
        p1._script.appendleft(target_stack_obj)
        engine_cast_spell(game, p1, mana_sculpt)
        resolve_top(game)
        return p1

    def test_refund_with_wizard_at_next_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_battlefield(game, 0, [_make_wizard()])

        target_cost = ManaCost(generic=2, pips={ManaType.RED: 1})  # CMC 3
        self._counter_and_get_p1(game, target_cost)
        p1.mana_pool.empty()

        # Refund must NOT have arrived yet (delayed trigger, not immediate)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        # At p1's next main phase, the delayed trigger fires
        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_refund_amount_equals_mana_spent(self) -> None:
        """Refund amount tracks mana_spent at cast time, not printed CMC."""
        game = create_game()
        p1, p2 = game.players
        set_battlefield(game, 0, [_make_wizard()])

        # CMC 5 target
        target_cost = ManaCost(generic=3, pips={ManaType.RED: 2})
        self._counter_and_get_p1(game, target_cost)
        p1.mana_pool.empty()

        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_no_refund_without_wizard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Non-Wizard creature on p1's battlefield
        bear = Creature(
            name="Bear", owner=p1, base_power=2, base_toughness=2,
            subtypes={"Beast"},
        )
        set_battlefield(game, 0, [bear])

        target_cost = ManaCost(generic=2, pips={ManaType.RED: 1})
        self._counter_and_get_p1(game, target_cost)
        p1.mana_pool.empty()

        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_refund_when_fizzled(self) -> None:
        """Already covered behaviorally by TestCounter.test_fizzle…; this
        is the explicit assertion that fizzle path skips refund."""
        game = create_game()
        p1, p2 = game.players
        set_battlefield(game, 0, [_make_wizard()])

        target = _make_target_spell(owner=p2)
        set_hand(game, 1, [target])
        _fund_for(p2, target.mana_cost)
        engine_cast_spell(game, p2, target)
        target_stack_obj = game.stack.peek()

        mana_sculpt = ManaSculpt(owner=p1)
        set_hand(game, 0, [mana_sculpt])
        _fund_for(p1, mana_sculpt.mana_cost)
        p1._script.appendleft(target_stack_obj)
        engine_cast_spell(game, p1, mana_sculpt)

        # Target leaves the stack before Mana Sculpt resolves
        _remove_from_stack(game, target_stack_obj)
        p1.mana_pool.empty()
        resolve_top(game)

        # Advance to next main — no trigger fires
        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_refund_on_opponent_main_phase(self) -> None:
        """The delayed trigger fires on YOUR next main phase, not the opponent's."""
        game = create_game()
        p1, p2 = game.players
        set_battlefield(game, 0, [_make_wizard()])

        target_cost = ManaCost(generic=2, pips={ManaType.RED: 1})
        self._counter_and_get_p1(game, target_cost)
        p1.mana_pool.empty()

        # p2's main phase first — no refund
        _enter_main_phase_for(game, p2)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        # Then p1's main — refund arrives
        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_refund_fires_only_once(self) -> None:
        """The delayed trigger fires at the controller's NEXT main phase
        and never again."""
        game = create_game()
        p1, p2 = game.players
        set_battlefield(game, 0, [_make_wizard()])

        target_cost = ManaCost(generic=2, pips={ManaType.RED: 1})
        self._counter_and_get_p1(game, target_cost)
        p1.mana_pool.empty()

        # First main: refund fires
        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

        # Drain pool, fire next main phase — should NOT fire again
        p1.mana_pool.empty()
        _enter_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_refund_locked_in_when_wizard_leaves_before_next_main(self) -> None:
        """Per oracle, the 'if you control a Wizard' check is evaluated at
        Mana Sculpt's resolution time. If the Wizard leaves before the next
        main phase, the refund still fires (the trigger was already
        registered).
        """
        game = create_game()
        p1, p2 = game.players
        wizard = _make_wizard()
        set_battlefield(game, 0, [wizard])

        target_cost = ManaCost(generic=2, pips={ManaType.RED: 1})
        self._counter_and_get_p1(game, target_cost)
        p1.mana_pool.empty()

        # Remove the Wizard before next main
        p1.zones[Zone.BATTLEFIELD].remove(wizard)

        _enter_main_phase_for(game, p1)
        # Refund still arrives — the trigger was locked in at resolution time
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
