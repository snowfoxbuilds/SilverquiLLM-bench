"""Audited tests for Disdainful Stroke (collector key soa_17).

Verifies the Disdainful Stroke card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import DisdainfulStroke

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDisdainfulStrokeBasicProperties:
    """Basic property tests for Disdainful Stroke."""

    def test_is_instant(self) -> None:
        """Disdainful Stroke must be a Instant subclass."""
        card = DisdainfulStroke(name="Disdainful Stroke", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """DisdainfulStroke.name must be 'Disdainful Stroke'."""
        card = DisdainfulStroke(name="Disdainful Stroke", owner=None)
        assert card.name == "Disdainful Stroke"

    def test_card_types(self) -> None:
        """Disdainful Stroke must have correct card types."""
        card = DisdainfulStroke(name="Disdainful Stroke", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Disdainful Stroke must have converted mana cost 2."""
        card = DisdainfulStroke(name="Disdainful Stroke", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Disdainful Stroke must have correct colors."""
        card = DisdainfulStroke(name="Disdainful Stroke", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestDisdainfulStrokeAbilities:
    """Ability tests for Disdainful Stroke — expected to fail against stubs."""

    def test_counters_spell(self) -> None:
        """Resolution should counter target spell."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target_spell = Instant(name="Enemy", owner=opponent)
        target_spell.controller = opponent
        game.stack.append(target_spell)
        stack_before = len(game.stack)
        card = DisdainfulStroke(name="Disdainful Stroke", owner=player)
        card.controller = player
        card._targets = [target_spell]
        if hasattr(card, "set_targets"):
            card.set_targets([target_spell])
        card.on_resolve(game)
        stack_after = len(game.stack)
        assert stack_after < stack_before, (
            f"Should counter: stack {stack_before} -> {stack_after}"
        )


@pytest.mark.edge
class TestDisdainfulStrokeEdgeCases:
    """Edge case tests for Disdainful Stroke."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DisdainfulStroke(name="Disdainful Stroke", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestDisdainfulStrokeInteractions:
    """Interaction tests for Disdainful Stroke."""

    def test_get_targets_finds_stack_spells(self) -> None:
        """get_targets should find spells on stack."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        spell = Instant(name="OnStack", owner=opponent)
        spell.controller = opponent
        game.stack.append(spell)
        card = DisdainfulStroke(name="Disdainful Stroke", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find spell on stack"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = DisdainfulStroke(name="Disdainful Stroke", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
