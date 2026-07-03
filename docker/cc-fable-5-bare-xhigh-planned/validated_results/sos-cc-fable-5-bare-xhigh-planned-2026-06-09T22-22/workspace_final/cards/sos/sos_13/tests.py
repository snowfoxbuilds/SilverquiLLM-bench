"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _names(zone):
    return [getattr(c, "name", "?") for c in zone.get_all()]


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class TestProperties:
    def test_bare_construction_and_name(self):
        c = EmeritusOfTruceSwordsToPlowshares()
        assert c.name == "Emeritus of Truce // Swords to Plowshares"
        assert c.base_power == 3 and c.base_toughness == 3
        assert {"Cat", "Cleric"} <= c.subtypes
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")


class TestSwordsToPlowshares:
    def test_exiles_and_gains_life(self):
        game = create_game()
        p0, p1 = game.players
        bear = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear], life=20)
        swords = SwordsToPlowshares(owner=p0, controller=p0)
        swords.chosen_targets = [bear]
        swords.on_resolve(game)
        assert game.get_exile(p1).contains(bear)
        assert p1.life == 24  # controller of exiled creature gains its power


class TestEmeritusETB:
    def test_token_created_for_target_player(self):
        game = create_game()
        p0 = game.players[0]
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[em],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.appendleft(p0)  # target player = you
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        bf = _names(game.get_battlefield(p0))
        assert "Inkling" in bf
        inkling = next(c for c in game.get_battlefield(p0).get_all()
                       if c.name == "Inkling")
        assert inkling.base_power == 1 and inkling.base_toughness == 1
        assert Keyword.FLYING in inkling.keywords

    def test_not_prepared_when_no_opponent_advantage(self):
        game = create_game()
        p0 = game.players[0]
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[em],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.appendleft(p0)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        assert em.prepared is False

    def test_becomes_prepared_when_opponent_has_more(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[em],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.appendleft(p0)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        # You control Emeritus + Inkling = 2; opponent has 3 > 2 → prepared.
        assert em.prepared is True
        assert "Swords to Plowshares" in _names(game.get_exile(p0))


class TestCastPrepared:
    def test_cast_prepared_exiles_and_unprepares(self):
        game = create_game()
        p0, p1 = game.players
        bears = _bears(3)
        set_board_state(game, 1, battlefield=bears, life=20)
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[em],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.appendleft(p0)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        assert em.prepared is True

        target = bears[0]
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p0._script.appendleft(target)
        assert em.cast_prepared(game) is True
        _drain(game)

        assert game.get_exile(p1).contains(target)
        assert p1.life == 22  # gained the exiled creature's power (2)
        assert em.prepared is False
        assert "Swords to Plowshares" in _names(game.get_graveyard(p0))

    def test_cannot_cast_prepared_without_target(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        em = EmeritusOfTruceSwordsToPlowshares(owner=None)
        set_board_state(game, 0, hand=[em],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.appendleft(p0)
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        # Remove all creatures from the board so there is no legal target.
        set_board_state(game, 1, battlefield=[])
        set_board_state(game, 0, battlefield=[], mana={ManaType.WHITE: 1})
        assert em.cast_prepared(game) is False
        assert em.prepared is True  # stays prepared
