"""Audited tests for Essence Scatter (collector key 47).

Verifies the Essence Scatter card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import EssenceScatter

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestEssenceScatterBasicProperties:
    """Basic property tests for Essence Scatter."""

    def test_is_instant(self) -> None:
        """Essence Scatter must be a Instant subclass."""
        card = EssenceScatter(name="Essence Scatter", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """EssenceScatter.name must be 'Essence Scatter'."""
        card = EssenceScatter(name="Essence Scatter", owner=None)
        assert card.name == "Essence Scatter"

    def test_card_types(self) -> None:
        """Essence Scatter must have correct card types."""
        card = EssenceScatter(name="Essence Scatter", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Essence Scatter must have converted mana cost 2."""
        card = EssenceScatter(name="Essence Scatter", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Essence Scatter must have correct colors."""
        card = EssenceScatter(name="Essence Scatter", owner=None)
        assert "U" in card_colors(card)

@pytest.mark.ability
class TestEssenceScatterAbilities:
    """Ability tests for Essence Scatter — expected to fail against stubs."""

    def test_counters_spell(self) -> None:
        """Resolution should counter target spell."""
        from test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        from engine.stack import StackObject
        from engine.types import Zone
        target_spell = Instant(name="Enemy", owner=opponent)
        target_spell.controller = opponent
        target_stack_obj = StackObject(source=target_spell, controller=opponent)
        game.stack.push(target_stack_obj)
        opponent.zones[Zone.STACK].add(target_spell)
        stack_before = len(game.stack)
        card = EssenceScatter(name="Essence Scatter", owner=player)
        card.controller = player
        card.chosen_targets = [target_stack_obj]
        card.on_resolve(game)
        stack_after = len(game.stack)
        assert stack_after < stack_before, (
            f"Should counter: stack {stack_before} -> {stack_after}"
        )

@pytest.mark.edge
class TestEssenceScatterEdgeCases:
    """Edge case tests for Essence Scatter."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = EssenceScatter(name="Essence Scatter", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestEssenceScatterInteractions:
    """Interaction tests for Essence Scatter."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = EssenceScatter(name="Essence Scatter", owner=player)
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
        card = EssenceScatter(name="Essence Scatter", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
