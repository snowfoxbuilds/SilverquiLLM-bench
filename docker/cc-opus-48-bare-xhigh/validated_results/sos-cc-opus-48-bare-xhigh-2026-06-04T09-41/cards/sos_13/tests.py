"""Tests for Emeritus of Truce // Swords to Plowshares (SOS #13)."""

from __future__ import annotations

from collections import deque
from typing import Any

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _vanilla(name: str, power: int = 2, toughness: int = 2) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}"),
        base_power=power,
        base_toughness=toughness,
    )


def _enter(game: Any, emeritus: EmeritusOfTruceSwordsToPlowshares) -> None:
    """Register triggers and fire the ETB event (set_board_state bypasses it)."""
    emeritus.register_triggers(game)
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=emeritus.controller),
    )
    _resolve_all(game)


def test_basic_characteristics():
    card = EmeritusOfTruceSwordsToPlowshares()
    assert card.base_power == 3 and card.base_toughness == 3
    assert {"Cat", "Cleric"} <= card.subtypes
    assert card.mana_cost.generic == 1
    assert not card.prepared
    # Its prepare spell is Swords to Plowshares ({W} instant).
    spell = card.prepare_spell_factory()
    assert isinstance(spell, SwordsToPlowshares)
    assert CardType.INSTANT in spell.card_types


def test_etb_creates_inkling_token_for_target_player():
    game = create_game()
    p1, p2 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(game, 0, battlefield=[emeritus])

    # Target the opponent for the token.
    p1._script = deque([p2])
    _enter(game, emeritus)

    inklings = [
        c for c in game.get_battlefield(p2).get_all()
        if getattr(c, "name", None) == "Inkling"
    ]
    assert len(inklings) == 1
    token = inklings[0]
    assert token.base_power == 1 and token.base_toughness == 1
    assert Keyword.FLYING in token.keywords
    assert "Inkling" in token.subtypes
    assert token.is_token


def test_becomes_prepared_when_opponent_has_more_creatures():
    game = create_game()
    p1, p2 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(game, 0, battlefield=[emeritus])
    set_board_state(game, 1, battlefield=[_vanilla("A"), _vanilla("B"), _vanilla("C")])

    # Token to p1: p1 ends with 2 creatures, p2 has 3 → opponent has more.
    p1._script = deque([p1])
    _enter(game, emeritus)

    assert emeritus.prepared
    # A castable copy of the prepare spell now sits in p1's exile.
    exiled = [
        c for c in game.get_exile(p1).get_all()
        if isinstance(c, SwordsToPlowshares)
    ]
    assert len(exiled) == 1


def test_not_prepared_when_opponent_has_fewer_creatures():
    game = create_game()
    p1, p2 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(game, 0, battlefield=[emeritus, _vanilla("Friend")])
    set_board_state(game, 1, battlefield=[_vanilla("Lonely")])

    p1._script = deque([p1])
    _enter(game, emeritus)

    assert not emeritus.prepared
    assert len(game.get_exile(p1).get_all()) == 0


def test_cast_prepared_exiles_creature_and_grants_life():
    game = create_game()
    p1, p2 = game.players

    emeritus = EmeritusOfTruceSwordsToPlowshares()
    set_board_state(game, 0, battlefield=[emeritus])
    set_board_state(game, 1, battlefield=[_vanilla("A"), _vanilla("B"), _vanilla("C")])
    p2.life = 20

    # Become prepared (opponent has more creatures).
    p1._script = deque([p1])
    _enter(game, emeritus)
    assert emeritus.prepared

    # A 3-power victim controlled by p2.
    victim = Creature(
        name="Victim", mana_cost=ManaCost.parse("{2}"), base_power=3, base_toughness=3
    )
    set_board_state(game, 1, battlefield=[victim])

    p1.mana_pool.add(ManaType.WHITE, 1)
    # cast_prepared -> cast_spell chooses target (the victim).
    p1._script = deque([victim])
    emeritus.cast_prepared(game)
    _resolve_all(game)

    # Victim exiled; its controller (p2) gained life equal to power (3).
    assert game.get_exile(p2).contains(victim)
    assert not game.get_battlefield(p2).contains(victim)
    assert p2.life == 23
    # Casting the prepared spell removes the designation.
    assert not emeritus.prepared
    assert len(game.get_exile(p1).get_all()) == 0
