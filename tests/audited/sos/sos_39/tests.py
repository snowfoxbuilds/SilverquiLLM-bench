"""Audited tests for Brush Off (collector key 39).

Verifies the Brush Off card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import BrushOff

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBrushOffBasicProperties:
    """Basic property tests for Brush Off."""

    def test_is_instant(self) -> None:
        """Brush Off must be a Instant subclass."""
        card = BrushOff(name="Brush Off", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """BrushOff.name must be 'Brush Off'."""
        card = BrushOff(name="Brush Off", owner=None)
        assert card.name == "Brush Off"

    def test_card_types(self) -> None:
        """Brush Off must have correct card types."""
        card = BrushOff(name="Brush Off", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Brush Off must have converted mana cost 4."""
        card = BrushOff(name="Brush Off", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Brush Off must have correct colors."""
        card = BrushOff(name="Brush Off", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestBrushOffAbilities:
    """Ability tests for Brush Off — expected to fail against stubs."""

    def test_counters_spell(self) -> None:
        """Resolution should counter target spell."""
        from tests.test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target_spell = Instant(name="Enemy", owner=opponent)
        target_spell.controller = opponent
        game.stack.append(target_spell)
        stack_before = len(game.stack)
        card = BrushOff(name="Brush Off", owner=player)
        card.controller = player
        card._targets = [target_spell]
        if hasattr(card, "set_targets"):
            card.set_targets([target_spell])
        card.on_resolve(game)
        stack_after = len(game.stack)
        assert stack_after < stack_before, (
            f"Should counter: stack {stack_before} -> {stack_after}"
        )

    def test_cost_reduction_applies(self) -> None:
        """cost_reduction should return > 0 when condition met."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = BrushOff(name="Brush Off", owner=player)
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
class TestBrushOffEdgeCases:
    """Edge case tests for Brush Off."""

    def test_no_reduction_when_condition_unmet(self) -> None:
        """No cost reduction when condition is not met."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = BrushOff(name="Brush Off", owner=player)
        card.controller = player
        target = Creature(name="Untapped", owner=player, base_power=2, base_toughness=2)
        target.tapped = False
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        reduction = card.cost_reduction(game)
        assert reduction == 0, f"No reduction when unmet, got {reduction}"


@pytest.mark.interaction
class TestBrushOffInteractions:
    """Interaction tests for Brush Off."""

    def test_get_targets_finds_stack_spells(self) -> None:
        """get_targets should find spells on stack."""
        from tests.test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        spell = Instant(name="OnStack", owner=opponent)
        spell.controller = opponent
        game.stack.append(spell)
        card = BrushOff(name="Brush Off", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find spell on stack"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = BrushOff(name="Brush Off", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
