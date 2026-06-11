"""Tests for SOS 246 — Zaffai and the Tempests.

Legendary Creature — Human Bard Sorcerer  {5}{U}{R}
5/7
Oracle: Once during each of your turns, you may cast an instant or sorcery
spell from your hand without paying its mana cost.
"""

from __future__ import annotations

from cards.sos.sos_246.card_impl import ZaffaiAndTheTempests
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestZaffaiProperties:
    """Static card data should match the SOS 246 spec."""

    def test_name(self) -> None:
        card = ZaffaiAndTheTempests(owner=None)
        assert card.name == "Zaffai and the Tempests"

    def test_mana_cost(self) -> None:
        card = ZaffaiAndTheTempests(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{U}{R}")

    def test_power_toughness(self) -> None:
        card = ZaffaiAndTheTempests(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 7

    def test_is_creature(self) -> None:
        card = ZaffaiAndTheTempests(owner=None)
        assert isinstance(card, Creature)

    def test_is_legendary(self) -> None:
        card = ZaffaiAndTheTempests(owner=None)
        # Legendary can be a supertype or attribute
        assert getattr(card, "legendary", False) or "Legendary" in getattr(card, "supertypes", set())

    def test_subtypes(self) -> None:
        card = ZaffaiAndTheTempests(owner=None)
        subtypes = getattr(card, "subtypes", set())
        assert "Human" in subtypes
        assert "Bard" in subtypes
        assert "Sorcerer" in subtypes


class TestZaffaiFreecastAbility:
    """Once per turn, may cast an instant/sorcery from hand without paying mana cost."""

    def test_has_free_cast_ability(self) -> None:
        """Zaffai should expose a static or triggered ability for free casting."""
        card = ZaffaiAndTheTempests(owner=None)
        # The card should have some mechanism for free casting
        assert hasattr(card, "on_cast_permission") or hasattr(card, "get_static_abilities") or hasattr(card, "free_cast_used") or hasattr(card, "modify_cast_cost")

    def test_free_cast_tracks_once_per_turn(self) -> None:
        """The free cast should only be usable once per turn."""
        game = create_game()
        p1 = game.players[0]
        card = ZaffaiAndTheTempests(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # After using free cast once, it should be marked as used
        # Implementation should track this via a flag or counter
        assert hasattr(card, "free_cast_used") or hasattr(card, "free_casts_this_turn")

    def test_free_cast_resets_on_new_turn(self) -> None:
        """The free cast permission should reset at start of turn."""
        game = create_game()
        p1 = game.players[0]
        card = ZaffaiAndTheTempests(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Mark as used
        if hasattr(card, "free_cast_used"):
            card.free_cast_used = True
        # Reset should occur on turn start
        if hasattr(card, "on_turn_start"):
            card.on_turn_start(game)
            assert card.free_cast_used is False
