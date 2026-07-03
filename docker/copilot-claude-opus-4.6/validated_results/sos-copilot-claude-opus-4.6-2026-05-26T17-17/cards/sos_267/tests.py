"""Tests for SOS 267 — Plains.

Basic Land — Plains
({T}: Add {W}.)
"""

from __future__ import annotations

from cards.sos.sos_267.card_impl import Plains
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType
from test_utils import create_game


class TestPlainsProperties:
    """Static card data should match the SOS 267 spec."""

    def test_is_land(self) -> None:
        card = Plains(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = Plains(owner=None)
        assert card.name == "Plains"

    def test_has_land_card_type(self) -> None:
        card = Plains(owner=None)
        assert CardType.LAND in card.card_types

    def test_is_basic(self) -> None:
        """Plains is a basic land."""
        from engine.types import Supertype
        card = Plains(owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_plains_subtype(self) -> None:
        card = Plains(owner=None)
        assert "Plains" in card.subtypes


class TestPlainsManaAbility:
    """{T}: Add {W}."""

    def test_has_mana_ability(self) -> None:
        card = Plains(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_produces_white_mana(self) -> None:
        card = Plains(owner=None)
        abilities = card.get_mana_abilities()
        white_found = any(
            ManaType.WHITE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert white_found is True

    def test_does_not_enter_tapped(self) -> None:
        """Basic lands enter untapped."""
        game = create_game()
        p1 = game.players[0]
        card = Plains(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False
