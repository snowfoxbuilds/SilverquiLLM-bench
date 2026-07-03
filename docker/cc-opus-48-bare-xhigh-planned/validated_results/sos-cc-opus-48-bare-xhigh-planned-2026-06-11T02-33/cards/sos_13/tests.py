"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, set_board_state


def _bears(n, power=2):
    return [Creature(name=f"Bear{i}", base_power=power, base_toughness=2) for i in range(n)]


def _cast_emeritus(game, target_player):
    p0 = game.players[0]
    set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                    mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
    p0._script.append(target_player)  # ETB "target player" for the Inkling
    cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
    return next(c for c in game.get_battlefield(p0).get_all()
                if c.name.startswith("Emeritus"))


class TestProperties:
    def test_emeritus_basics(self):
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_swords_basics(self):
        s = SwordsToPlowshares(owner=None)
        assert isinstance(s, Instant)
        assert s.name == "Swords to Plowshares"
        assert s.mana_cost == ManaCost.parse("{W}")

    def test_swords_no_creatures_no_target(self):
        game = create_game()
        assert SwordsToPlowshares(owner=None).get_targets(game) == []


class TestETB:
    def test_creates_flying_inkling_for_target(self):
        game = create_game()
        p0, p1 = game.players
        _cast_emeritus(game, p0)
        inkling = next((c for c in game.get_battlefield(p0).get_all()
                        if c.name == "Inkling"), None)
        assert inkling is not None
        assert inkling.base_power == 1 and inkling.base_toughness == 1
        assert Keyword.FLYING in inkling.keywords

    def test_inkling_can_go_to_opponent(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        emeritus = _cast_emeritus(game, p1)  # token to opponent
        assert any(c.name == "Inkling" for c in game.get_battlefield(p1).get_all())
        # p1: 2 bears + Inkling = 3 > p0 (Emeritus only = 1) → prepared
        assert emeritus.is_prepared is True


class TestPrepared:
    def test_becomes_prepared_when_opponent_has_more(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(3))
        emeritus = _cast_emeritus(game, p0)
        assert emeritus.is_prepared is True

    def test_not_prepared_when_you_have_enough(self):
        game = create_game()
        p0, p1 = game.players
        emeritus = _cast_emeritus(game, p0)  # nobody else has creatures
        assert emeritus.is_prepared is False

    def test_cast_prepared_swords_exiles_and_gains_life(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=_bears(3, power=2))
        emeritus = _cast_emeritus(game, p0)
        assert emeritus.is_prepared is True
        victim = game.get_battlefield(p1).get_all()[0]
        assert emeritus.cast_prepared(game, target=victim) is True
        resolve_top(game)  # resolve the prepared Swords copy
        assert game.get_exile(p1).contains(victim)  # exiled
        assert p1.life == 22                         # controller gains power (2)
        assert emeritus.is_prepared is False         # unprepared

    def test_cast_prepared_when_not_prepared_is_noop(self):
        game = create_game()
        p0, p1 = game.players
        emeritus = _cast_emeritus(game, p0)  # not prepared
        assert emeritus.cast_prepared(game) is False
