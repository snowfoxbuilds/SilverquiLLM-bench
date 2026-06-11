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
from test_utils import create_game, cast_spell, set_board_state

FULL_NAME = "Emeritus of Truce // Swords to Plowshares"
CAST_MANA = {ManaType.WHITE: 2, ManaType.COLORLESS: 1}


def _cast_emeritus(game, token_to, opp_creatures=0):
    """Cast Emeritus for p1, with opp_creatures bears for p2 first."""
    p1, p2 = game.players
    bears = [
        Creature(name=f"Bear{i}", base_power=2, base_toughness=2)
        for i in range(opp_creatures)
    ]
    if bears:
        set_board_state(game, 1, battlefield=bears)
    card = EmeritusOfTruceSwordsToPlowshares(owner=p1)
    set_board_state(game, 0, hand=[card], mana=CAST_MANA)
    p1._script.append(token_to)  # ETB: target player for the Inkling
    cast_spell(game, 0, FULL_NAME)
    return card


class TestBasics:
    def test_constructs_bare_with_full_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == FULL_NAME
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes


class TestEnterTrigger:
    def test_token_created_not_prepared_when_boards_equal(self):
        game = create_game()
        p1, p2 = game.players
        card = _cast_emeritus(game, token_to=p1, opp_creatures=0)

        inklings = [
            c for c in game.get_battlefield(p1).get_all() if c.name == "Inkling"
        ]
        assert len(inklings) == 1
        tok = inklings[0]
        assert tok.power == 1 and tok.toughness == 1
        assert Keyword.FLYING in tok.keywords
        assert tok.is_token
        # p1 controls 2 creatures (Emeritus + token), p2 none → not prepared.
        assert card.prepared is False
        assert len(p1.zones[Zone.EXILE]) == 0

    def test_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p1, p2 = game.players
        card = _cast_emeritus(game, token_to=p2, opp_creatures=2)

        # p2: 2 bears + Inkling = 3 creatures; p1: Emeritus = 1 → prepared.
        assert card.prepared is True
        copies = [
            c
            for c in p1.zones[Zone.EXILE].get_all()
            if c.name == "Swords to Plowshares"
        ]
        assert len(copies) == 1


class TestPreparedSpell:
    def test_cast_copy_exiles_creature_and_unprepares(self):
        game = create_game()
        p1, p2 = game.players
        card = _cast_emeritus(game, token_to=p2, opp_creatures=2)
        assert card.prepared

        bear = next(
            c for c in game.get_battlefield(p2).get_all() if c.name == "Bear0"
        )
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p1._script.append(bear)  # target for Swords to Plowshares
        card.cast_prepared_spell(game)
        resolve_top(game)

        assert p2.zones[Zone.EXILE].contains(bear)
        assert p2.life == 22  # gained life equal to the bear's power
        assert card.prepared is False
        assert p1.mana_pool.total() == 0  # {W} was paid
        # The exiled copy left exile when cast.
        assert not any(
            c.name == "Swords to Plowshares"
            for c in p1.zones[Zone.EXILE].get_all()
        )

    def test_cannot_cast_copy_without_mana(self):
        game = create_game()
        p1, p2 = game.players
        card = _cast_emeritus(game, token_to=p2, opp_creatures=2)
        set_board_state(game, 0, mana={})
        with pytest.raises(CastingError):
            card.cast_prepared_spell(game)
        assert card.prepared is True  # still prepared, copy still in exile

    def test_cannot_cast_when_not_prepared(self):
        game = create_game()
        p1, p2 = game.players
        card = _cast_emeritus(game, token_to=p1, opp_creatures=0)
        assert card.prepared is False
        with pytest.raises(CastingError):
            card.cast_prepared_spell(game)

    def test_copy_ceases_when_emeritus_leaves_battlefield(self):
        from engine.game import exile as exile_permanent

        game = create_game()
        p1, p2 = game.players
        card = _cast_emeritus(game, token_to=p2, opp_creatures=2)
        assert card.prepared

        exile_permanent(game, card)
        resolve_top(game)  # the leaves-battlefield unprepare trigger

        assert not any(
            c.name == "Swords to Plowshares"
            for c in p1.zones[Zone.EXILE].get_all()
        )
        assert card.prepared is False
