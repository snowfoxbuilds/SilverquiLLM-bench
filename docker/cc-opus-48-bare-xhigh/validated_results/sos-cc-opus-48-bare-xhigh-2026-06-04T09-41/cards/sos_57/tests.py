"""Tests for Mana Sculpt (SOS #57)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _victim_instant() -> Instant:
    return Instant(name="Victim Spell", mana_cost=ManaCost.parse("{3}"))


def _wizard() -> Creature:
    return Creature(
        name="Merfolk Wizard",
        mana_cost=ManaCost.parse("{1}{U}"),
        subtypes={"Merfolk", "Wizard"},
        base_power=1,
        base_toughness=1,
    )


def test_is_instant():
    card = ManaSculpt()
    assert CardType.INSTANT in card.card_types
    assert card.mana_cost.generic == 1


def test_counters_target_spell():
    game = create_game()
    p1, p2 = game.players

    victim = _victim_instant()
    set_board_state(game, 1, hand=[victim])
    p2.mana_pool.add(ManaType.COLORLESS, 3)
    engine_cast(game, p2, victim)
    victim_obj = game.stack.peek()
    assert victim_obj.source is victim

    sculpt = ManaSculpt()
    set_board_state(game, 0, hand=[sculpt])
    p1.mana_pool.add(ManaType.COLORLESS, 1)
    p1.mana_pool.add(ManaType.BLUE, 2)
    from collections import deque

    p1._script = deque([victim_obj])
    engine_cast(game, p1, sculpt)

    _resolve_all(game)

    # Victim spell countered → in p2 graveyard, not on battlefield.
    assert game.get_graveyard(p2).contains(victim)
    assert not game.get_battlefield(p2).contains(victim)


def test_wizard_grants_delayed_mana():
    game = create_game()
    p1, p2 = game.players

    set_board_state(game, 0, battlefield=[_wizard()])

    victim = _victim_instant()
    set_board_state(game, 1, hand=[victim])
    p2.mana_pool.add(ManaType.COLORLESS, 3)
    engine_cast(game, p2, victim)
    victim_obj = game.stack.peek()

    sculpt = ManaSculpt()
    set_board_state(game, 0, hand=[sculpt])
    p1.mana_pool.add(ManaType.COLORLESS, 1)
    p1.mana_pool.add(ManaType.BLUE, 2)
    from collections import deque

    p1._script = deque([victim_obj])
    engine_cast(game, p1, sculpt)
    _resolve_all(game)

    # p1's pool is now empty (spent on Mana Sculpt).
    assert p1.mana_pool.total() == 0

    # Opponent's main phase: no mana for p1.
    game.trigger_manager.fire_event(
        game, BeginningOfMainPhaseTriggeredEvent(player=p2)
    )
    _resolve_all(game)
    assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    # p1's next main phase: delayed mana arrives (3 {C} = mana spent on victim).
    game.trigger_manager.fire_event(
        game, BeginningOfMainPhaseTriggeredEvent(player=p1)
    )
    _resolve_all(game)
    assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    # Fires only once — a later main phase yields no more mana.
    p1.mana_pool.empty()
    game.trigger_manager.fire_event(
        game, BeginningOfMainPhaseTriggeredEvent(player=p1)
    )
    _resolve_all(game)
    assert p1.mana_pool.get(ManaType.COLORLESS) == 0


def test_no_wizard_no_delayed_mana():
    game = create_game()
    p1, p2 = game.players

    victim = _victim_instant()
    set_board_state(game, 1, hand=[victim])
    p2.mana_pool.add(ManaType.COLORLESS, 3)
    engine_cast(game, p2, victim)
    victim_obj = game.stack.peek()

    sculpt = ManaSculpt()
    set_board_state(game, 0, hand=[sculpt])
    p1.mana_pool.add(ManaType.COLORLESS, 1)
    p1.mana_pool.add(ManaType.BLUE, 2)
    from collections import deque

    p1._script = deque([victim_obj])
    engine_cast(game, p1, sculpt)
    _resolve_all(game)

    game.trigger_manager.fire_event(
        game, BeginningOfMainPhaseTriggeredEvent(player=p1)
    )
    _resolve_all(game)
    assert p1.mana_pool.get(ManaType.COLORLESS) == 0
