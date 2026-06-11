"""Tests for SOS 252 — Strixhaven Skycoach.

Artifact — Vehicle with:
- Flying
- When this Vehicle enters, you may search your library for a basic land card,
  reveal it, put it into your hand, then shuffle.
- Crew 2
- 3/2
"""

from __future__ import annotations

from cards.sos.sos_252.card_impl import StrixhavenSkycoach
from engine.card import Artifact
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game


class TestStrixhavenSkycoachProperties:
    """Static card data should match the SOS 252 spec."""

    def test_name(self) -> None:
        card = StrixhavenSkycoach(owner=None)
        assert card.name == "Strixhaven Skycoach"

    def test_mana_cost(self) -> None:
        card = StrixhavenSkycoach(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}")

    def test_is_artifact(self) -> None:
        card = StrixhavenSkycoach(owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types

    def test_is_vehicle_subtype(self) -> None:
        card = StrixhavenSkycoach(owner=None)
        assert "Vehicle" in card.subtypes

    def test_power_toughness(self) -> None:
        card = StrixhavenSkycoach(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_has_flying(self) -> None:
        card = StrixhavenSkycoach(owner=None)
        assert Keyword.FLYING in card.keywords


class TestStrixhavenSkycoachCrew:
    """Crew 2: Tap creatures with total power >= 2 to animate."""

    def test_crew_value_is_two(self) -> None:
        card = StrixhavenSkycoach(owner=None)
        assert card.crew_cost == 2

    def test_not_creature_by_default(self) -> None:
        """A Vehicle is not a creature until crewed."""
        card = StrixhavenSkycoach(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_becomes_creature_when_crewed(self) -> None:
        """After crewing, the Vehicle should become an artifact creature."""
        game = create_game()
        p1 = game.players[0]
        card = StrixhavenSkycoach(owner=p1, controller=p1)
        card.crew(game, p1)
        assert CardType.CREATURE in card.card_types


class TestStrixhavenSkycoachETB:
    """When this Vehicle enters, you may search library for a basic land."""

    def test_etb_trigger_searches_for_basic_land(self) -> None:
        """On entering the battlefield, the player may find a basic land."""
        game = create_game()
        p1 = game.players[0]
        card = StrixhavenSkycoach(owner=p1, controller=p1)
        # Put a basic land in the library for the search to find
        from engine.card import Land
        basic_land = Land(owner=p1, controller=p1, name="Forest")
        basic_land.supertypes = {"Basic"}
        p1.zones[Zone.LIBRARY].add(basic_land)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        card.on_enter_battlefield(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before + 1

    def test_etb_with_no_basic_land_in_library(self) -> None:
        """If no basic land is in library, the search finds nothing."""
        game = create_game()
        p1 = game.players[0]
        card = StrixhavenSkycoach(owner=p1, controller=p1)
        # Empty library — no basic lands
        hand_before = len(p1.zones[Zone.HAND].get_all())
        card.on_enter_battlefield(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before

    def test_etb_is_optional(self) -> None:
        """The search is 'you may' — declining leaves hand unchanged."""
        game = create_game()
        p1 = game.players[0]
        card = StrixhavenSkycoach(owner=p1, controller=p1)
        # If the player declines, nothing happens
        # This is modeled by passing may_choice=False or similar
        hand_before = len(p1.zones[Zone.HAND].get_all())
        card.on_enter_battlefield(game, may_choice=False)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before
