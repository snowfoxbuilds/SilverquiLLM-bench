"""Tests for Emeritus of Truce // Swords to Plowshares (sos_13)."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.casting import CastingError, resolve_top
from engine.types import Keyword, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell

NAME = "Emeritus of Truce // Swords to Plowshares"


def _bears(n, prefix="Bear"):
    return [Creature(name=f"{prefix} {i}", base_power=2, base_toughness=2) for i in range(n)]


def _cast_emeritus(game, token_player):
    """Cast Emeritus through the real engine; ETB token goes to token_player."""
    p0 = game.players[0]
    set_board_state(game, 0,
                    hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                    mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
    p0._script.append(token_player)
    cast_spell(game, 0, NAME)
    for c in game.get_battlefield(p0).get_all():
        if c.name == NAME:
            return c
    raise AssertionError("Emeritus not on battlefield")


class TestEmeritusOfTruce:
    def test_constructs_bare_with_full_name(self):
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == NAME
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_etb_creates_inkling_for_target_player(self):
        game = create_game()
        p0, p1 = game.players
        emeritus = _cast_emeritus(game, p1)
        inklings = [c for c in game.get_battlefield(p1).get_all() if c.name == "Inkling"]
        assert len(inklings) == 1
        token = inklings[0]
        assert token.is_token
        assert token.power == 1 and token.toughness == 1
        assert Keyword.FLYING in token.keywords
        # p1 now has 1 creature, p0 has 1 (Emeritus): not more -> unprepared.
        assert not emeritus.is_prepared

    def test_becomes_prepared_when_opponent_has_more_creatures(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        emeritus = _cast_emeritus(game, p1)  # token to opponent: 3 vs 1
        assert emeritus.is_prepared
        # The prepare-spell copy sits in exile (rule 722.3c).
        exiled = [c for c in p0.zones[Zone.EXILE].get_all()
                  if c.name == "Swords to Plowshares"]
        assert len(exiled) == 1

    def test_cast_prepared_spell_exiles_creature_gains_life(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        emeritus = _cast_emeritus(game, p1)
        assert emeritus.is_prepared
        target = game.get_battlefield(p1).get_all()[0]
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        p0._script.append(target)  # spell target
        emeritus.cast_prepared_spell(game)
        while not game.stack.is_empty():
            resolve_top(game)
        assert p1.zones[Zone.EXILE].contains(target)
        assert p1.life == 22  # gains life equal to its power (2)
        assert not emeritus.is_prepared
        # The copy ceased to exist — not in exile or graveyard.
        assert all(c.name != "Swords to Plowshares"
                   for c in p0.zones[Zone.EXILE].get_all())
        assert all(c.name != "Swords to Plowshares"
                   for c in p0.zones[Zone.GRAVEYARD].get_all())

    def test_cannot_cast_when_not_prepared(self):
        game = create_game()
        p0, p1 = game.players
        emeritus = _cast_emeritus(game, p0)  # opponent has no creatures
        assert not emeritus.is_prepared
        with pytest.raises(CastingError):
            emeritus.cast_prepared_spell(game)

    def test_prepared_cast_requires_white_mana(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        emeritus = _cast_emeritus(game, p1)
        set_board_state(game, 0, mana={})  # pool emptied
        with pytest.raises(CastingError):
            emeritus.cast_prepared_spell(game)
        assert emeritus.is_prepared  # still prepared, copy still in exile
