"""Audited tests for Feed the Swarm (collector key soa_29).

Verifies the Feed the Swarm card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import FeedTheSwarm

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestFeedTheSwarmBasicProperties:
    """Basic property tests for Feed the Swarm."""

    def test_is_sorcery(self) -> None:
        """Feed the Swarm must be a Sorcery subclass."""
        card = FeedTheSwarm(name="Feed the Swarm", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """FeedTheSwarm.name must be 'Feed the Swarm'."""
        card = FeedTheSwarm(name="Feed the Swarm", owner=None)
        assert card.name == "Feed the Swarm"

    def test_card_types(self) -> None:
        """Feed the Swarm must have correct card types."""
        card = FeedTheSwarm(name="Feed the Swarm", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Feed the Swarm must have converted mana cost 2."""
        card = FeedTheSwarm(name="Feed the Swarm", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Feed the Swarm must have correct colors."""
        card = FeedTheSwarm(name="Feed the Swarm", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestFeedTheSwarmAbilities:
    """Ability tests for Feed the Swarm — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = FeedTheSwarm(name="Feed the Swarm", owner=player)
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

    def test_causes_life_loss(self) -> None:
        """Resolution should cause life loss."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = FeedTheSwarm(name="Feed the Swarm", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )


@pytest.mark.edge
class TestFeedTheSwarmEdgeCases:
    """Edge case tests for Feed the Swarm."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = FeedTheSwarm(name="Feed the Swarm", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestFeedTheSwarmInteractions:
    """Interaction tests for Feed the Swarm."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = FeedTheSwarm(name="Feed the Swarm", owner=player)
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
        card = FeedTheSwarm(name="Feed the Swarm", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
