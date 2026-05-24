"""Audited tests for Growth Curve (collector key 193).

Verifies the Growth Curve card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import GrowthCurve

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestGrowthCurveBasicProperties:
    """Basic property tests for Growth Curve."""

    def test_is_sorcery(self) -> None:
        """Growth Curve must be a Sorcery subclass."""
        card = GrowthCurve(name="Growth Curve", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """GrowthCurve.name must be 'Growth Curve'."""
        card = GrowthCurve(name="Growth Curve", owner=None)
        assert card.name == "Growth Curve"

    def test_card_types(self) -> None:
        """Growth Curve must have correct card types."""
        card = GrowthCurve(name="Growth Curve", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Growth Curve must have converted mana cost 2."""
        card = GrowthCurve(name="Growth Curve", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Growth Curve must have correct colors."""
        card = GrowthCurve(name="Growth Curve", owner=None)
        assert "G" in card.colors
        assert "U" in card.colors


@pytest.mark.ability
class TestGrowthCurveAbilities:
    """Ability tests for Growth Curve — expected to fail against stubs."""

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = GrowthCurve(name="Growth Curve", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        power_before = target.base_power
        card.on_resolve(game)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"+1/+1 counter: power {power_before} -> {power_after}"
        )


@pytest.mark.edge
class TestGrowthCurveEdgeCases:
    """Edge case tests for Growth Curve."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = GrowthCurve(name="Growth Curve", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestGrowthCurveInteractions:
    """Interaction tests for Growth Curve."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = GrowthCurve(name="Growth Curve", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = GrowthCurve(name="Growth Curve", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
