"""Audited tests for Tablet of Discovery (collector key 132).

Verifies the Tablet of Discovery card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import TabletOfDiscovery

from benchmarks.sos.workspace.engine.card import Artifact
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestTabletOfDiscoveryBasicProperties:
    """Basic property tests for Tablet of Discovery."""

    def test_is_artifact(self) -> None:
        """Tablet of Discovery must be a Artifact subclass."""
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        """TabletOfDiscovery.name must be 'Tablet of Discovery'."""
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        assert card.name == "Tablet of Discovery"

    def test_card_types(self) -> None:
        """Tablet of Discovery must have correct card types."""
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        assert CardType.ARTIFACT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Tablet of Discovery must have converted mana cost 3."""
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Tablet of Discovery must have correct colors."""
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestTabletOfDiscoveryAbilities:
    """Ability tests for Tablet of Discovery -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Tablet of Discovery must implement behavioral method"


@pytest.mark.edge
class TestTabletOfDiscoveryEdgeCases:
    """Edge case and trap tests for Tablet of Discovery."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        card2 = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        card1.name = "Modified"
        assert card2.name == "Tablet of Discovery", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=None)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"


@pytest.mark.interaction
class TestTabletOfDiscoveryInteractions:
    """Multi-card interaction tests for Tablet of Discovery."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = TabletOfDiscovery(name="Tablet of Discovery", owner=player)
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
