"""Audited tests for Giant Growth (collector key soa_52).

Verifies the Giant Growth card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import GiantGrowth

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestGiantGrowthBasicProperties:
    """Basic property tests for Giant Growth."""

    def test_is_instant(self) -> None:
        """Giant Growth must be a Instant subclass."""
        card = GiantGrowth(name="Giant Growth", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """GiantGrowth.name must be 'Giant Growth'."""
        card = GiantGrowth(name="Giant Growth", owner=None)
        assert card.name == "Giant Growth"

    def test_card_types(self) -> None:
        """Giant Growth must have correct card types."""
        card = GiantGrowth(name="Giant Growth", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Giant Growth must have converted mana cost 1."""
        card = GiantGrowth(name="Giant Growth", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Giant Growth must have correct colors."""
        card = GiantGrowth(name="Giant Growth", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestGiantGrowthAbilities:
    """Ability tests for Giant Growth — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +3/+3."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = GiantGrowth(name="Giant Growth", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 4, (
            f"Should pump to 4 power, got {actual_power}"
        )


@pytest.mark.edge
class TestGiantGrowthEdgeCases:
    """Edge case tests for Giant Growth."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GiantGrowth(name="Giant Growth", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestGiantGrowthInteractions:
    """Interaction tests for Giant Growth."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = GiantGrowth(name="Giant Growth", owner=player)
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
        card = GiantGrowth(name="Giant Growth", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
