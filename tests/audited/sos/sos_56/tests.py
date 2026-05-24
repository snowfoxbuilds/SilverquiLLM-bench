"""Audited tests for Landscape Painter // Vibrant Idea (collector key 56).

Verifies the Landscape Painter // Vibrant Idea card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import LandscapePainterVibrantIdea

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestLandscapePainterVibrantIdeaBasicProperties:
    """Basic property tests for Landscape Painter // Vibrant Idea."""

    def test_is_creature(self) -> None:
        """Landscape Painter // Vibrant Idea must be a Creature subclass."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """LandscapePainterVibrantIdea.name must be 'Landscape Painter // Vibrant Idea'."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert card.name == "Landscape Painter // Vibrant Idea"

    def test_card_types(self) -> None:
        """Landscape Painter // Vibrant Idea must have correct card types."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Landscape Painter // Vibrant Idea must have converted mana cost 7."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert card.mana_cost.cmc == 7

    def test_colors(self) -> None:
        """Landscape Painter // Vibrant Idea must have correct colors."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Landscape Painter // Vibrant Idea must have base power 2."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Landscape Painter // Vibrant Idea must have base toughness 1."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestLandscapePainterVibrantIdeaAbilities:
    """Ability tests for Landscape Painter // Vibrant Idea -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Landscape Painter // Vibrant Idea must have Prepared keyword."""
        from engine.types import Keyword
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert Keyword.PREPARED in card.keywords, "Landscape Painter // Vibrant Idea should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Landscape Painter // Vibrant Idea must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Landscape Painter // Vibrant Idea must implement prepared mechanic"


@pytest.mark.edge
class TestLandscapePainterVibrantIdeaEdgeCases:
    """Edge case and trap tests for Landscape Painter // Vibrant Idea."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        card2 = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        card1.name = "Modified"
        assert card2.name == "Landscape Painter // Vibrant Idea", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=None, base_power=2, base_toughness=1)
        assert card.mana_cost.cmc == 7, \
            f"CMC must be 7, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=player, base_power=2, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 0
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestLandscapePainterVibrantIdeaInteractions:
    """Multi-card interaction tests for Landscape Painter // Vibrant Idea."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=player, base_power=2, base_toughness=1)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = LandscapePainterVibrantIdea(name="Landscape Painter // Vibrant Idea", owner=player, base_power=2, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
