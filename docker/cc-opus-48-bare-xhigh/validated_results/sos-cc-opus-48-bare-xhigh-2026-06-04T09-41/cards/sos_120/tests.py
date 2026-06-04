"""Tests for Improvisation Capstone (SOS #120)."""

from __future__ import annotations

from collections import deque
from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaType, ManaCost, Phase, Zone
from test_utils import create_game, set_board_state


def _bear(name: str, mv: int = 2) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(f"{{{mv}}}"),
        base_power=2,
        base_toughness=2,
    )


def _stack_library(game: Any, idx: int, cards_top_first: list[Any]) -> None:
    """Set the library so cards_top_first[0] is the top (drawn/exiled first)."""
    player = game.players[idx]
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in reversed(cards_top_first):
        c.owner = player
        c.controller = player
        lib.add(c)


def _add_capstone_mana(player: Any) -> None:
    player.mana_pool.add(ManaType.COLORLESS, 5)
    player.mana_pool.add(ManaType.RED, 2)


def test_basic_characteristics():
    card = ImprovisationCapstone()
    assert CardType.SORCERY in card.card_types
    assert "Lesson" in card.subtypes
    assert card.mana_cost.generic == 5


def test_impulse_exiles_until_mv_four():
    game = create_game()
    p1, p2 = game.players

    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone])
    _add_capstone_mana(p1)

    a, b, c = _bear("A", 2), _bear("B", 2), _bear("C", 5)
    _stack_library(game, 0, [a, b, c])

    # Decline all free casts.
    p1._script = deque([None])

    from test_utils import cast_spell

    cast_spell(game, 0, "Improvisation Capstone")

    exile = game.get_exile(p1)
    # Exiled A (2) then B (total 4) → stop. C remains on top of library.
    assert exile.contains(a)
    assert exile.contains(b)
    assert not exile.contains(c)
    assert game.get_library(p1).contains(c)
    # Paradigm: the capstone itself is exiled (not in graveyard).
    assert exile.contains(capstone)
    assert not game.get_graveyard(p1).contains(capstone)
    # Declined free casts → bears stay in exile.
    assert not game.get_battlefield(p1).contains(a)


def test_free_casts_exiled_spell():
    game = create_game()
    p1, p2 = game.players

    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone])
    _add_capstone_mana(p1)

    a, b = _bear("A", 2), _bear("B", 2)
    _stack_library(game, 0, [a, b])

    # Cast A for free, then stop.
    p1._script = deque([a, None])

    from test_utils import cast_spell

    cast_spell(game, 0, "Improvisation Capstone")

    # A was free-cast → on the battlefield. B stayed in exile.
    assert game.get_battlefield(p1).contains(a)
    assert game.get_exile(p1).contains(b)
    assert not game.get_exile(p1).contains(a)


def test_paradigm_recurs_on_first_main_phase():
    game = create_game()
    p1, p2 = game.players

    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone])
    _add_capstone_mana(p1)

    a, b, c, d = _bear("A", 2), _bear("B", 2), _bear("C", 2), _bear("D", 2)
    _stack_library(game, 0, [a, b, c, d])

    # Initial resolve: decline free casts.  Recurrence: accept, decline casts.
    p1._script = deque([None, True, None])

    from test_utils import cast_spell

    cast_spell(game, 0, "Improvisation Capstone")
    # First impulse exiled A and B.
    assert game.get_exile(p1).contains(a)
    assert game.get_exile(p1).contains(b)
    assert game.get_library(p1).contains(c)

    # The recurring trigger fires at the controller's precombat main phase.
    assert game.phase == Phase.PRECOMBAT_MAIN
    game.trigger_manager.fire_event(
        game, BeginningOfMainPhaseTriggeredEvent(player=p1)
    )
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)

    # Second impulse exiled C and D.
    assert game.get_exile(p1).contains(c)
    assert game.get_exile(p1).contains(d)
