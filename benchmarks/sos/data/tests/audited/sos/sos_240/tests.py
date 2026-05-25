"""Audited tests for Vibrant Outburst (collector key 240).

Verifies the Vibrant Outburst card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import VibrantOutburst

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestVibrantOutburstBasicProperties:
    """Basic property tests for Vibrant Outburst."""

    def test_is_instant(self) -> None:
        """Vibrant Outburst must be a Instant subclass."""
        card = VibrantOutburst(name="Vibrant Outburst", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """VibrantOutburst.name must be 'Vibrant Outburst'."""
        card = VibrantOutburst(name="Vibrant Outburst", owner=None)
        assert card.name == "Vibrant Outburst"

    def test_card_types(self) -> None:
        """Vibrant Outburst must have correct card types."""
        card = VibrantOutburst(name="Vibrant Outburst", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Vibrant Outburst must have converted mana cost 2."""
        card = VibrantOutburst(name="Vibrant Outburst", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Vibrant Outburst must have correct colors."""
        card = VibrantOutburst(name="Vibrant Outburst", owner=None)
        assert "R" in card.colors
        assert "U" in card.colors


@pytest.mark.ability
class TestVibrantOutburstAbilities:
    """Ability tests for Vibrant Outburst — expected to fail against stubs."""

    def test_deals_damage(self) -> None:
        """Resolution should deal 3 damage."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = VibrantOutburst(name="Vibrant Outburst", owner=player)
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
class TestVibrantOutburstEdgeCases:
    """Edge case tests for Vibrant Outburst."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = VibrantOutburst(name="Vibrant Outburst", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestVibrantOutburstInteractions:
    """Interaction tests for Vibrant Outburst."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = VibrantOutburst(name="Vibrant Outburst", owner=player)
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
        card = VibrantOutburst(name="Vibrant Outburst", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
