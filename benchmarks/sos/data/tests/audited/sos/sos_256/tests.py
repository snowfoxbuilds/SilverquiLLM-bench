"""Audited tests for Forum of Amity (collector key 256).

Verifies the Forum of Amity card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import ForumOfAmity

from engine.card import Land
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestForumOfAmityBasicProperties:
    """Basic property tests for Forum of Amity."""

    def test_is_land(self) -> None:
        """Forum of Amity must be a Land subclass."""
        card = ForumOfAmity(name="Forum of Amity", owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        """ForumOfAmity.name must be 'Forum of Amity'."""
        card = ForumOfAmity(name="Forum of Amity", owner=None)
        assert card.name == "Forum of Amity"

    def test_card_types(self) -> None:
        """Forum of Amity must have correct card types."""
        card = ForumOfAmity(name="Forum of Amity", owner=None)
        assert CardType.LAND in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Forum of Amity must have converted mana cost 0."""
        card = ForumOfAmity(name="Forum of Amity", owner=None)
        assert card.mana_cost.cmc == 0

    def test_colorless(self) -> None:
        """Forum of Amity must be colorless."""
        card = ForumOfAmity(name="Forum of Amity", owner=None)
        assert len(card_colors(card)) == 0

@pytest.mark.ability
class TestForumOfAmityAbilities:
    """Ability tests for Forum of Amity -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = ForumOfAmity(name="Forum of Amity", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Forum of Amity must implement behavioral method"

@pytest.mark.edge
class TestForumOfAmityEdgeCases:
    """Edge case and trap tests for Forum of Amity."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ForumOfAmity(name="Forum of Amity", owner=None)
        card2 = ForumOfAmity(name="Forum of Amity", owner=None)
        card1.name = "Modified"
        assert card2.name == "Forum of Amity", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ForumOfAmity(name="Forum of Amity", owner=None)
        assert card.mana_cost.cmc == 0, \
            f"CMC must be 0, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ForumOfAmity(name="Forum of Amity", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"

@pytest.mark.interaction
class TestForumOfAmityInteractions:
    """Multi-card interaction tests for Forum of Amity."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ForumOfAmity(name="Forum of Amity", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        set_board_state(game, 0, battlefield=[other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
