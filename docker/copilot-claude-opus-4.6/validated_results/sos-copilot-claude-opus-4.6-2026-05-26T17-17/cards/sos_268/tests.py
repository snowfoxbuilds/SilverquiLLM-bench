"""Tests for SOS 268 — Island.

Basic Land — Island
({T}: Add {U}.)
"""

from __future__ import annotations

from cards.sos.sos_268.card_impl import Island
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType
from test_utils import create_game


class TestIslandProperties:
    """Static card data should match the SOS 268 spec."""

    def test_is_land(self) -> None:
        card = Island(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = Island(owner=None)
        assert card.name == "Island"

    def test_has_land_card_type(self) -> None:
        card = Island(owner=None)
        assert CardType.LAND in card.card_types

    def test_is_basic(self) -> None:
        from engine.types import Supertype
        card = Island(owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_island_subtype(self) -> None:
        card = Island(owner=None)
        assert "Island" in card.subtypes


class TestIslandManaAbility:
    """{T}: Add {U}."""

    def test_has_mana_ability(self) -> None:
        card = Island(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_produces_blue_mana(self) -> None:
        card = Island(owner=None)
        abilities = card.get_mana_abilities()
        blue_found = any(
            ManaType.BLUE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert blue_found is True

    def test_does_not_enter_tapped(self) -> None:
        """Basic lands enter untapped."""
        game = create_game()
        p1 = game.players[0]
        card = Island(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False
