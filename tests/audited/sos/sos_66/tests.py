"""Audited tests for Run Behind (collector key 66).

Verifies the Run Behind card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import RunBehind

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRunBehindBasicProperties:
    """Basic property tests for Run Behind."""

    def test_is_instant(self) -> None:
        """Run Behind must be a Instant subclass."""
        card = RunBehind(name="Run Behind", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """RunBehind.name must be 'Run Behind'."""
        card = RunBehind(name="Run Behind", owner=None)
        assert card.name == "Run Behind"

    def test_card_types(self) -> None:
        """Run Behind must have correct card types."""
        card = RunBehind(name="Run Behind", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Run Behind must have converted mana cost 4."""
        card = RunBehind(name="Run Behind", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Run Behind must have correct colors."""
        card = RunBehind(name="Run Behind", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestRunBehindAbilities:
    """Ability tests for Run Behind — expected to fail against stubs."""

    def test_cost_reduction_applies(self) -> None:
        """cost_reduction should return > 0 when condition met."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = RunBehind(name="Run Behind", owner=player)
        card.controller = player
        target = Creature(name="Cond", owner=player, base_power=2, base_toughness=2)
        target.tapped = True
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        reduction = card.cost_reduction(game)
        assert reduction > 0, f"Cost reduction should apply, got {reduction}"


@pytest.mark.edge
class TestRunBehindEdgeCases:
    """Edge case tests for Run Behind."""

    def test_no_reduction_when_condition_unmet(self) -> None:
        """No cost reduction when condition is not met."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = RunBehind(name="Run Behind", owner=player)
        card.controller = player
        target = Creature(name="Untapped", owner=player, base_power=2, base_toughness=2)
        target.tapped = False
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        reduction = card.cost_reduction(game)
        assert reduction == 0, f"No reduction when unmet, got {reduction}"


@pytest.mark.interaction
class TestRunBehindInteractions:
    """Interaction tests for Run Behind."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = RunBehind(name="Run Behind", owner=player)
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
        card = RunBehind(name="Run Behind", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
