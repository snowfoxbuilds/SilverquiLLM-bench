"""Tests for SOS 61 — Muse's Encouragement."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_61.card_impl import MusesEncouragement
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestMusesEncouragementProperties:
    """Static card data should match the SOS 61 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(MusesEncouragement(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = MusesEncouragement(owner=None)
        assert card.name == "Muse's Encouragement"
        assert card.mana_cost == ManaCost.parse("{4}{U}")


class TestMusesEncouragementResolution:
    """Muse's Encouragement should create the token and surveil 2."""

    def test_creates_a_3_3_blue_and_red_elemental_token_with_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = MusesEncouragement(owner=p1, controller=p1)

        spell.on_resolve(game)

        battlefield = game.get_battlefield(p1).get_all()
        assert len(battlefield) == 1
        token = battlefield[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert "Elemental" in token.subtypes
        assert get_colors(token) == {Color.BLUE, Color.RED}
        assert Keyword.FLYING in token.keywords
        assert token.power == 3
        assert token.toughness == 3

    def test_surveil_two_moves_only_the_chosen_card_into_the_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        second = CardImpl(name="Second Card", owner=p1, controller=p1)
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(second)
        game.get_library(p1).add(top)
        p1._script.extend([True, False])

        spell = MusesEncouragement(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert game.get_graveyard(p1).contains(top)
        assert not game.get_graveyard(p1).contains(second)
        assert game.get_library(p1).contains(bottom)
        assert game.get_library(p1).contains(second)
        assert not game.get_library(p1).contains(top)
