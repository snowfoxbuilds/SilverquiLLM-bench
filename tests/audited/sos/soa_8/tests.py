"""Audited tests for Repel Calamity (collector key soa_8).

Verifies the Repel Calamity card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import RepelCalamity

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRepelCalamityBasicProperties:
    """Basic property tests for Repel Calamity."""

    def test_is_instant(self) -> None:
        """Repel Calamity must be a Instant subclass."""
        card = RepelCalamity(name="Repel Calamity", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """RepelCalamity.name must be 'Repel Calamity'."""
        card = RepelCalamity(name="Repel Calamity", owner=None)
        assert card.name == "Repel Calamity"

    def test_card_types(self) -> None:
        """Repel Calamity must have correct card types."""
        card = RepelCalamity(name="Repel Calamity", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Repel Calamity must have converted mana cost 2."""
        card = RepelCalamity(name="Repel Calamity", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Repel Calamity must have correct colors."""
        card = RepelCalamity(name="Repel Calamity", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestRepelCalamityAbilities:
    """Ability tests for Repel Calamity — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = RepelCalamity(name="Repel Calamity", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        bf_before = len(game.get_battlefield(opponent).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(opponent).get_all())
        assert bf_after < bf_before, (
            f"Target should be destroyed: bf {bf_before} -> {bf_after}"
        )


@pytest.mark.edge
class TestRepelCalamityEdgeCases:
    """Edge case tests for Repel Calamity."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = RepelCalamity(name="Repel Calamity", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestRepelCalamityInteractions:
    """Interaction tests for Repel Calamity."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = RepelCalamity(name="Repel Calamity", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = RepelCalamity(name="Repel Calamity", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
