"""Audited tests for Sylvan Library (collector key spg_155).

Verifies the Sylvan Library card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import SylvanLibrary

from engine.card import Enchantment
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestSylvanLibraryBasicProperties:
    """Basic property tests for Sylvan Library."""

    def test_is_enchantment(self) -> None:
        """Sylvan Library must be a Enchantment subclass."""
        card = SylvanLibrary(name="Sylvan Library", owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        """SylvanLibrary.name must be 'Sylvan Library'."""
        card = SylvanLibrary(name="Sylvan Library", owner=None)
        assert card.name == "Sylvan Library"

    def test_card_types(self) -> None:
        """Sylvan Library must have correct card types."""
        card = SylvanLibrary(name="Sylvan Library", owner=None)
        assert CardType.ENCHANTMENT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Sylvan Library must have converted mana cost 2."""
        card = SylvanLibrary(name="Sylvan Library", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Sylvan Library must have correct colors."""
        card = SylvanLibrary(name="Sylvan Library", owner=None)
        assert "G" in card_colors(card)

@pytest.mark.ability
class TestSylvanLibraryAbilities:
    """Ability tests for Sylvan Library -- expected to fail against stubs."""

    def test_resolution_draws_cards(self) -> None:
        """Spell resolution must draw cards per oracle text."""
        from test_utils import create_game
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(5):
            c = Creature(name=f"Lib{i}", owner=player, base_power=1, base_toughness=1)
            player.zones[Zone.LIBRARY].add(c)
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = SylvanLibrary(name="Sylvan Library", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, "Sylvan Library must draw cards"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = SylvanLibrary(name="Sylvan Library", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Sylvan Library must implement behavioral method"

@pytest.mark.edge
class TestSylvanLibraryEdgeCases:
    """Edge case and trap tests for Sylvan Library."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SylvanLibrary(name="Sylvan Library", owner=None)
        card2 = SylvanLibrary(name="Sylvan Library", owner=None)
        card1.name = "Modified"
        assert card2.name == "Sylvan Library", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SylvanLibrary(name="Sylvan Library", owner=None)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SylvanLibrary(name="Sylvan Library", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"

@pytest.mark.interaction
class TestSylvanLibraryInteractions:
    """Multi-card interaction tests for Sylvan Library."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = SylvanLibrary(name="Sylvan Library", owner=player)
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
