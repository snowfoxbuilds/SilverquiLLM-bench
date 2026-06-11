"""Tests for SOS 11 — Eager Glyphmage.

A 3/3 Cat Cleric for {3}{W} with ETB: create a 1/1 white and black
Inkling creature token with flying.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_11.card_impl import EagerGlyphmage
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestEagerGlyphmageProperties:
    """Static card data should match the SOS 11 spec."""

    def test_is_creature(self) -> None:
        card = EagerGlyphmage(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert EagerGlyphmage(owner=None).name == "Eager Glyphmage"

    def test_mana_cost(self) -> None:
        assert EagerGlyphmage(owner=None).mana_cost == ManaCost.parse("{3}{W}")

    def test_power_toughness(self) -> None:
        card = EagerGlyphmage(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEagerGlyphmageETB:
    """When this creature enters, create a 1/1 W/B Inkling with flying."""

    def test_etb_creates_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EagerGlyphmage(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        before = len(bf.get_all())
        card.on_resolve(game)
        after = len(bf.get_all())
        # Should create at least one token (the Inkling)
        assert after - before >= 1

    def test_token_is_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EagerGlyphmage(owner=p1, controller=p1)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, "is_token", False)]
        assert len(tokens) >= 1

    def test_token_has_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EagerGlyphmage(owner=p1, controller=p1)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, "is_token", False)]
        assert len(tokens) >= 1
        token = tokens[0]
        assert Keyword.FLYING in token.keywords

    def test_token_is_one_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EagerGlyphmage(owner=p1, controller=p1)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, "is_token", False)]
        assert len(tokens) >= 1
        token = tokens[0]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_token_is_named_inkling(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EagerGlyphmage(owner=p1, controller=p1)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, "is_token", False)]
        assert len(tokens) >= 1
        token = tokens[0]
        assert "Inkling" in token.name
