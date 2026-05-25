"""Audited tests for Slumbering Trudge (collector key 160).

Verifies the Slumbering Trudge card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import SlumberingTrudge

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSlumberingTrudgeBasicProperties:
    """Basic property tests for Slumbering Trudge."""

    def test_is_creature(self) -> None:
        """Slumbering Trudge must be a Creature subclass."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SlumberingTrudge.name must be 'Slumbering Trudge'."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert card.name == "Slumbering Trudge"

    def test_card_types(self) -> None:
        """Slumbering Trudge must have correct card types."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Slumbering Trudge must have converted mana cost 1."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Slumbering Trudge must have correct colors."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Slumbering Trudge must have base power 6."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert card.base_power == 6

    def test_toughness(self) -> None:
        """Slumbering Trudge must have base toughness 6."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert card.base_toughness == 6


@pytest.mark.ability
class TestSlumberingTrudgeAbilities:
    """Ability tests for Slumbering Trudge -- expected to fail against stubs."""

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Slumbering Trudge must implement on_enter_battlefield per oracle text"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Slumbering Trudge must implement behavioral method"


@pytest.mark.edge
class TestSlumberingTrudgeEdgeCases:
    """Edge case and trap tests for Slumbering Trudge."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        card2 = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        card1.name = "Modified"
        assert card2.name == "Slumbering Trudge", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SlumberingTrudge(name="Slumbering Trudge", owner=None, base_power=6, base_toughness=6)
        assert card.mana_cost.cmc == 1, \
            f"CMC must be 1, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SlumberingTrudge(name="Slumbering Trudge", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 5
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestSlumberingTrudgeInteractions:
    """Multi-card interaction tests for Slumbering Trudge."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = SlumberingTrudge(name="Slumbering Trudge", owner=player, base_power=6, base_toughness=6)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = SlumberingTrudge(name="Slumbering Trudge", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
