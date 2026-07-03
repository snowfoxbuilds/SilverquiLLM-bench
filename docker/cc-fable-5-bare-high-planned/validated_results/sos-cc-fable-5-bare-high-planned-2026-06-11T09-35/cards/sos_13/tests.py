"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature
from engine.casting import CastingError, resolve_top
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _cast_emeritus(game, target_player, opp_creatures=0):
    """Cast Emeritus through the real engine with its ETB pre-registered.

    The engine fires ENTERS_BATTLEFIELD before calling the entering card's
    own register_triggers, so the trigger is registered up front (the same
    convention engine_tests use).
    """
    p1 = game.players[0]
    bears = [Creature(name=f"Opp Bear {i}", base_power=2, base_toughness=2)
             for i in range(opp_creatures)]
    if bears:
        set_board_state(game, 1, battlefield=bears)
    card = EmeritusOfTruceSwordsToPlowshares(owner=None)
    set_board_state(game, 0, hand=[card],
                    mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
    card.owner = p1
    card.controller = p1
    card.register_triggers(game)
    p1._script.append(target_player)  # ETB: target player
    cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
    return card


class TestEmeritusStatic:
    def test_bare_construction_and_full_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.prepared is False


class TestEmeritusETB:
    def test_target_player_creates_inkling_token(self):
        game = create_game()
        p1 = game.players[0]
        card = _cast_emeritus(game, target_player=p1, opp_creatures=0)

        tokens = [c for c in p1.zones[Zone.BATTLEFIELD].get_all()
                  if getattr(c, "name", "") == "Inkling"]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.is_token
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords
        # Opponent has 0 creatures vs our 2 — not prepared.
        assert card.prepared is False
        assert len(p1.zones[Zone.EXILE]) == 0

    def test_becomes_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p1, p2 = game.players
        # Opponent has 2 bears; token goes to the opponent → 3 vs our 1.
        card = _cast_emeritus(game, target_player=p2, opp_creatures=2)

        assert card.prepared is True
        copies = [c for c in p1.zones[Zone.EXILE].get_all()
                  if getattr(c, "name", "") == "Swords to Plowshares"]
        assert len(copies) == 1, "the prepare-spell copy is created in exile"
        assert p2.zones[Zone.BATTLEFIELD].contains(card) is False


class TestPreparedCast:
    def _prepared_setup(self):
        game = create_game()
        p1, p2 = game.players
        card = _cast_emeritus(game, target_player=p2, opp_creatures=2)
        assert card.prepared
        return game, p1, p2, card

    def test_cast_copy_exiles_creature_and_unprepares(self):
        game, p1, p2, card = self._prepared_setup()
        bear = next(c for c in p2.zones[Zone.BATTLEFIELD].get_all()
                    if c.name == "Opp Bear 0")
        copy = card._prepared_copy
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p1._script.append(bear)  # Swords target
        card.cast_prepared_spell(game)
        while not game.stack.is_empty():
            resolve_top(game)

        assert p2.zones[Zone.EXILE].contains(bear), "creature exiled"
        assert p2.life == 22, "its controller gained life equal to power 2"
        assert card.prepared is False, "casting the copy unprepares"
        # The spell copy ceased to exist — not in graveyard, not in exile.
        assert not p1.zones[Zone.GRAVEYARD].contains(copy)
        assert not p1.zones[Zone.EXILE].contains(copy)
        assert p1.mana_pool.total() == 0, "the {W} was paid"

    def test_cannot_cast_when_not_prepared(self):
        game = create_game()
        p1 = game.players[0]
        card = _cast_emeritus(game, target_player=p1, opp_creatures=0)
        assert card.prepared is False
        with pytest.raises(CastingError):
            card.cast_prepared_spell(game)

    def test_cannot_cast_without_paying_w(self):
        game, p1, p2, card = self._prepared_setup()
        set_board_state(game, 0, mana={})  # no mana
        with pytest.raises(CastingError):
            card.cast_prepared_spell(game)
        assert card.prepared is True, "still prepared after a failed cast"

    def test_copy_ceases_when_emeritus_leaves_battlefield(self):
        from engine.game import destroy

        game, p1, p2, card = self._prepared_setup()
        copy = card._prepared_copy
        destroy(game, card)
        while not game.stack.is_empty():
            resolve_top(game)

        assert p1.zones[Zone.GRAVEYARD].contains(card)
        assert not p1.zones[Zone.EXILE].contains(copy), \
            "the uncast copy ceases to exist when the permanent leaves"
        assert card.prepared is False
