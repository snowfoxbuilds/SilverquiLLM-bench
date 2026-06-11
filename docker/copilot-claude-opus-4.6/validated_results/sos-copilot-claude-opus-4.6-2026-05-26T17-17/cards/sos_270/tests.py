"""Tests for SOS 270 — Mountain.

Basic Land — Mountain
({T}: Add {R}.)
"""

from __future__ import annotations

from cards.sos.sos_270.card_impl import Mountain
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType
from test_utils import create_game


class TestMountainProperties:
    """Static card data should match the SOS 270 spec."""

    def test_is_land(self) -> None:
        card = Mountain(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = Mountain(owner=None)
        assert card.name == "Mountain"

    def test_has_land_card_type(self) -> None:
        card = Mountain(owner=None)
        assert CardType.LAND in card.card_types

    def test_is_basic(self) -> None:
        from engine.types import Supertype
        card = Mountain(owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_mountain_subtype(self) -> None:
        card = Mountain(owner=None)
        assert "Mountain" in card.subtypes


class TestMountainManaAbility:
    """{T}: Add {R}."""

    def test_has_mana_ability(self) -> None:
        card = Mountain(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_produces_red_mana(self) -> None:
        card = Mountain(owner=None)
        abilities = card.get_mana_abilities()
        red_found = any(
            ManaType.RED in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert red_found is True

    def test_does_not_enter_tapped(self) -> None:
        """Basic lands enter untapped."""
        game = create_game()
        p1 = game.players[0]
        card = Mountain(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False
