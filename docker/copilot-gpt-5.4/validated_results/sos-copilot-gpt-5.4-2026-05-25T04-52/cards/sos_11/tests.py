"""Tests for SOS 11 — Eager Glyphmage."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_11.card_impl import EagerGlyphmage
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestEagerGlyphmageProperties:
    """Static card data should match the SOS 11 spec."""

    def test_is_cat_cleric_creature(self) -> None:
        card = EagerGlyphmage(owner=None)
        assert isinstance(card, Creature)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = EagerGlyphmage(owner=None)
        assert card.name == "Eager Glyphmage"
        assert card.mana_cost == ManaCost.parse("{3}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEagerGlyphmageResolution:
    """The ETB text should create the printed Inkling token."""

    def test_on_resolve_creates_a_white_and_black_flying_inkling_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EagerGlyphmage(owner=p1, controller=p1)

        card.on_resolve(game)

        tokens = game.get_battlefield(p1).get_all()
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert token.power == 1
        assert token.toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords
        assert get_colors(token) == {Color.WHITE, Color.BLACK}
