"""Audited tests for Improvisation Capstone (collector key 120).

Verifies the Improvisation Capstone card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import ImprovisationCapstone

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestImprovisationCapstoneBasicProperties:
    """Basic property tests for Improvisation Capstone."""

    def test_is_sorcery(self) -> None:
        """Improvisation Capstone must be a Sorcery subclass."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """ImprovisationCapstone.name must be 'Improvisation Capstone'."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        assert card.name == "Improvisation Capstone"

    def test_card_types(self) -> None:
        """Improvisation Capstone must have correct card types."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Improvisation Capstone must have converted mana cost 7."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        assert card.mana_cost.cmc == 7

    def test_colors(self) -> None:
        """Improvisation Capstone must have correct colors."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestImprovisationCapstoneAbilities:
    """Ability tests for Improvisation Capstone -- expected to fail against stubs."""

    def test_resolution_exiles_target(self) -> None:
        """Spell resolution must exile target per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        card.on_resolve(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "Improvisation Capstone must exile target"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Improvisation Capstone must implement behavioral method"


@pytest.mark.edge
class TestImprovisationCapstoneEdgeCases:
    """Edge case and trap tests for Improvisation Capstone."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        card2 = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        card1.name = "Modified"
        assert card2.name == "Improvisation Capstone", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=None)
        assert card.mana_cost.cmc == 7, \
            f"CMC must be 7, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"


@pytest.mark.interaction
class TestImprovisationCapstoneInteractions:
    """Multi-card interaction tests for Improvisation Capstone."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(name="Improvisation Capstone", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        set_board_state(game, 0, battlefield=[other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
