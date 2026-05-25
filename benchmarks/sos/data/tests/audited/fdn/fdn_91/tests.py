"""Audited tests for FDN 91 — Kellan, Planar Trailblazer."""

from __future__ import annotations

from card_impl import KellanPlanarTrailblazer
from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype, Zone
from test_utils import create_game


class TestKellanBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = KellanPlanarTrailblazer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = KellanPlanarTrailblazer(owner=None)
        assert card.name == "Kellan, Planar Trailblazer"

    def test_mana_cost(self) -> None:
        card = KellanPlanarTrailblazer(owner=None)
        assert card.mana_cost == ManaCost.parse("{R}")

    def test_power_toughness(self) -> None:
        card = KellanPlanarTrailblazer(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_is_legendary(self) -> None:
        card = KellanPlanarTrailblazer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = KellanPlanarTrailblazer(owner=None)
        assert "Scout" in card.subtypes
        assert "Human" in card.subtypes
        assert "Faerie" in card.subtypes


class TestKellanActivatedAbilities:
    """Two level-up style activated abilities."""

    def test_has_two_activated_abilities(self) -> None:
        card = KellanPlanarTrailblazer(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 2

    def test_scout_to_detective(self) -> None:
        """First ability: Scout → Detective."""
        game = create_game()
        p1 = game.players[0]
        card = KellanPlanarTrailblazer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities()
        # Directly call effect (skip mana cost for testing)
        abilities[0].effect(game)
        assert "Detective" in card.subtypes
        assert "Scout" not in card.subtypes

    def test_detective_to_rogue(self) -> None:
        """Second ability: Detective → Rogue with 3/2 and double strike."""
        game = create_game()
        p1 = game.players[0]
        card = KellanPlanarTrailblazer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # First become Detective
        card.subtypes = {"Human", "Faerie", "Detective"}
        abilities = card.get_activated_abilities()
        abilities[1].effect(game)
        assert "Rogue" in card.subtypes
        assert "Detective" not in card.subtypes
        assert card.modified_power == 3
        assert card.modified_toughness == 2
        kw = getattr(card, "keywords", Keyword(0)) or Keyword(0)
        assert kw & Keyword.DOUBLE_STRIKE

    def test_scout_ability_does_nothing_if_not_scout(self) -> None:
        """First ability only works if currently a Scout."""
        game = create_game()
        p1 = game.players[0]
        card = KellanPlanarTrailblazer(owner=p1, controller=p1)
        card.subtypes = {"Human", "Faerie", "Detective"}
        abilities = card.get_activated_abilities()
        abilities[0].effect(game)
        # Should still be Detective, not change
        assert "Detective" in card.subtypes

    def test_detective_ability_does_nothing_if_not_detective(self) -> None:
        """Second ability only works if currently a Detective."""
        game = create_game()
        p1 = game.players[0]
        card = KellanPlanarTrailblazer(owner=p1, controller=p1)
        # Still a Scout
        abilities = card.get_activated_abilities()
        abilities[1].effect(game)
        assert "Scout" in card.subtypes
        assert card.base_power == 2
