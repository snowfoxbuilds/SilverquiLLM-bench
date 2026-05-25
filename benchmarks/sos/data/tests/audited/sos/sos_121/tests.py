"""Audited tests for Living History (collector key 121).

Verifies the Living History card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import LivingHistory

from engine.card import Enchantment
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestLivingHistoryBasicProperties:
    """Basic property tests for Living History."""

    def test_is_enchantment(self) -> None:
        """Living History must be a Enchantment subclass."""
        card = LivingHistory(name="Living History", owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        """LivingHistory.name must be 'Living History'."""
        card = LivingHistory(name="Living History", owner=None)
        assert card.name == "Living History"

    def test_card_types(self) -> None:
        """Living History must have correct card types."""
        card = LivingHistory(name="Living History", owner=None)
        assert CardType.ENCHANTMENT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Living History must have converted mana cost 2."""
        card = LivingHistory(name="Living History", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Living History must have correct colors."""
        card = LivingHistory(name="Living History", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestLivingHistoryAbilities:
    """Ability tests for Living History — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = LivingHistory(name="Living History", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_pump_effect(self) -> None:
        """Resolution should grant +2/+0."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = LivingHistory(name="Living History", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 3, (
            f"Should pump to 3 power, got {actual_power}"
        )


@pytest.mark.edge
class TestLivingHistoryEdgeCases:
    """Edge case tests for Living History."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = LivingHistory(name="Living History", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestLivingHistoryInteractions:
    """Interaction tests for Living History."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = LivingHistory(name="Living History", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = LivingHistory(name="Living History", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
