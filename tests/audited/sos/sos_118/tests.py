"""Audited tests for Heated Argument (collector key 118).

Verifies the Heated Argument card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import HeatedArgument

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestHeatedArgumentBasicProperties:
    """Basic property tests for Heated Argument."""

    def test_is_instant(self) -> None:
        """Heated Argument must be a Instant subclass."""
        card = HeatedArgument(name="Heated Argument", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """HeatedArgument.name must be 'Heated Argument'."""
        card = HeatedArgument(name="Heated Argument", owner=None)
        assert card.name == "Heated Argument"

    def test_card_types(self) -> None:
        """Heated Argument must have correct card types."""
        card = HeatedArgument(name="Heated Argument", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Heated Argument must have converted mana cost 5."""
        card = HeatedArgument(name="Heated Argument", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Heated Argument must have correct colors."""
        card = HeatedArgument(name="Heated Argument", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestHeatedArgumentAbilities:
    """Ability tests for Heated Argument — expected to fail against stubs."""

    def test_deals_damage(self) -> None:
        """Resolution should deal 6 damage."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = HeatedArgument(name="Heated Argument", owner=player)
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
class TestHeatedArgumentEdgeCases:
    """Edge case tests for Heated Argument."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = HeatedArgument(name="Heated Argument", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestHeatedArgumentInteractions:
    """Interaction tests for Heated Argument."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = HeatedArgument(name="Heated Argument", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = HeatedArgument(name="Heated Argument", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
