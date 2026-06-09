"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature, Instant
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _cast_emeritus(game, target_player_index, p1_creatures):
    p0, p1 = game.players
    if p1_creatures:
        set_board_state(game, 1, battlefield=p1_creatures)
    em = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
    set_board_state(game, 0, hand=[em],
                    mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
    p0._script.appendleft(game.players[target_player_index])
    cast_spell(game, 0, "Emeritus of Truce")
    return em


class TestProperties:
    def test_front_face(self):
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in c.card_types
        assert {"Cat", "Cleric"} <= c.subtypes
        assert c.base_power == 3 and c.base_toughness == 3
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_back_face(self):
        s = SwordsToPlowshares(owner=None)
        assert isinstance(s, Instant)
        assert s.mana_cost == ManaCost.parse("{W}")


class TestETB:
    def test_creates_inkling_for_target_player(self):
        game = create_game()
        p0, p1 = game.players
        _cast_emeritus(game, 1, [])  # Inkling to p1
        inklings = [o for o in game.get_battlefield(p1).get_all()
                    if o.name == "Inkling"]
        assert len(inklings) == 1
        ink = inklings[0]
        assert Keyword.FLYING in ink.keywords
        assert ink.base_power == 1 and ink.base_toughness == 1

    def test_becomes_prepared_when_opponent_has_more(self):
        game = create_game()
        em = _cast_emeritus(game, 0, _bears(3))  # Inkling to p0
        # p0: Emeritus + Inkling = 2; p1: 3 → opponent has more → prepared.
        assert em.prepared is True

    def test_not_prepared_when_not_outnumbered(self):
        game = create_game()
        em = _cast_emeritus(game, 0, _bears(1))  # Inkling to p0
        # p0: Emeritus + Inkling = 2; p1: 1 → not outnumbered.
        assert em.prepared is False


class TestPreparedCast:
    def test_cast_swords_exiles_and_gains_life(self):
        game = create_game()
        p0, p1 = game.players
        bears = _bears(3)
        em = _cast_emeritus(game, 0, bears)
        assert em.prepared is True
        target_bear = bears[0]
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p1.life = 20
        p0._script.appendleft(target_bear)
        assert em.cast_prepared_spell(game) is True
        _resolve_stack(game)
        # Bear exiled; its controller (p1) gains life = power 2.
        assert game.get_exile(p1).contains(target_bear)
        assert not game.get_battlefield(p1).contains(target_bear)
        assert p1.life == 22
        # Casting unprepares.
        assert em.prepared is False

    def test_cannot_cast_when_not_prepared(self):
        game = create_game()
        em = _cast_emeritus(game, 0, _bears(1))  # not prepared
        assert em.prepared is False
        assert em.cast_prepared_spell(game) is False
