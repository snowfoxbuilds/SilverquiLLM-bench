"""Audited tests for Stress Dream (collector key 235).

Verifies the Stress Dream card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import StressDream

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestStressDreamBasicProperties:
    """Basic property tests for Stress Dream."""

    def test_is_instant(self) -> None:
        """Stress Dream must be a Instant subclass."""
        card = StressDream(name="Stress Dream", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """StressDream.name must be 'Stress Dream'."""
        card = StressDream(name="Stress Dream", owner=None)
        assert card.name == "Stress Dream"

    def test_card_types(self) -> None:
        """Stress Dream must have correct card types."""
        card = StressDream(name="Stress Dream", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Stress Dream must have converted mana cost 5."""
        card = StressDream(name="Stress Dream", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Stress Dream must have correct colors."""
        card = StressDream(name="Stress Dream", owner=None)
        assert "R" in card_colors(card)
        assert "U" in card_colors(card)

@pytest.mark.ability
class TestStressDreamAbilities:
    """Ability tests for Stress Dream — expected to fail against stubs."""

    def test_deals_damage(self) -> None:
        """Resolution should deal 5 damage."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = StressDream(name="Stress Dream", owner=player)
        card.controller = player
        card._targets = [opponent]
        if hasattr(card, "set_targets"):
            card.set_targets([opponent])
        card.on_resolve(game)
        life_after = opponent.life
        assert life_after < life_before, (
            f"Should deal damage: life {life_before} -> {life_after}"
        )

@pytest.mark.edge
class TestStressDreamEdgeCases:
    """Edge case tests for Stress Dream."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = StressDream(name="Stress Dream", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestStressDreamInteractions:
    """Interaction tests for Stress Dream."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = StressDream(name="Stress Dream", owner=player)
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
        card = StressDream(name="Stress Dream", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
