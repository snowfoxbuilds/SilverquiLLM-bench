"""Tests for SOS 269 — Swamp.

Basic Land — Swamp
({T}: Add {B}.)
"""

from __future__ import annotations

from cards.sos.sos_269.card_impl import Swamp
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType
from test_utils import create_game


class TestSwampProperties:
    """Static card data should match the SOS 269 spec."""

    def test_is_land(self) -> None:
        card = Swamp(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = Swamp(owner=None)
        assert card.name == "Swamp"

    def test_has_land_card_type(self) -> None:
        card = Swamp(owner=None)
        assert CardType.LAND in card.card_types

    def test_is_basic(self) -> None:
        from engine.types import Supertype
        card = Swamp(owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_swamp_subtype(self) -> None:
        card = Swamp(owner=None)
        assert "Swamp" in card.subtypes


class TestSwampManaAbility:
    """{T}: Add {B}."""

    def test_has_mana_ability(self) -> None:
        card = Swamp(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_produces_black_mana(self) -> None:
        card = Swamp(owner=None)
        abilities = card.get_mana_abilities()
        black_found = any(
            ManaType.BLACK in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert black_found is True

    def test_does_not_enter_tapped(self) -> None:
        """Basic lands enter untapped."""
        game = create_game()
        p1 = game.players[0]
        card = Swamp(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False
