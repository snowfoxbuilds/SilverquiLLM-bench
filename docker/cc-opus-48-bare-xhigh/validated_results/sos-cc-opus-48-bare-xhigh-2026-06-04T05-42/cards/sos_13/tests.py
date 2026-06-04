"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestProperties:
    def test_is_creature(self) -> None:
        assert isinstance(EmeritusOfTruceSwordsToPlowshares(owner=None), Creature)

    def test_name(self) -> None:
        assert (
            EmeritusOfTruceSwordsToPlowshares(owner=None).name
            == "Emeritus of Truce // Swords to Plowshares"
        )

    def test_mana_cost(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(
            owner=None
        ).mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness_and_types(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert (c.base_power, c.base_toughness) == (3, 3)
        assert {"Cat", "Cleric"} <= c.subtypes

    def test_starts_unprepared(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None).is_prepared is False


class TestEnterToken:
    def test_creates_inkling_for_target_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.chosen_targets = [p2]
        emeritus.on_resolve(game)
        tokens = [
            c
            for c in game.get_battlefield(p2).get_all()
            if getattr(c, "is_token", False)
        ]
        assert len(tokens) == 1
        tok = tokens[0]
        assert (tok.base_power, tok.base_toughness) == (1, 1)
        assert Keyword.FLYING in tok.keywords
        assert set(tok.colors) == {"W", "B"}

    def test_default_target_is_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.on_resolve(game)
        assert any(
            getattr(c, "is_token", False)
            for c in game.get_battlefield(p1).get_all()
        )


class TestPrepare:
    def test_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2"), _bear("B3")])
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.chosen_targets = [p1]
        emeritus.on_resolve(game)
        # p1 after token: 1 creature + Emeritus (on stack) = 2 < 3.
        assert emeritus.is_prepared is True

    def test_not_prepared_when_even(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("B1")])
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.chosen_targets = [p1]
        emeritus.on_resolve(game)
        assert emeritus.is_prepared is False


class TestSwordsToPlowshares:
    def test_cast_prepared_exiles_and_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        victim = Creature(name="Big", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[victim], life=20)
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.is_prepared = True

        result = emeritus.cast_prepared(game, victim)
        assert result is True
        assert p2.zones[Zone.EXILE].contains(victim)
        assert p2.life == 24
        assert emeritus.is_prepared is False

    def test_cast_prepared_requires_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        victim = Creature(name="Big", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[victim])
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.is_prepared = False
        assert emeritus.cast_prepared(game, victim) is False

    def test_cast_prepared_requires_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        victim = Creature(name="Big", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[victim])
        set_board_state(game, 0, mana={})
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emeritus.is_prepared = True
        assert emeritus.cast_prepared(game, victim) is False
        assert emeritus.is_prepared is True
