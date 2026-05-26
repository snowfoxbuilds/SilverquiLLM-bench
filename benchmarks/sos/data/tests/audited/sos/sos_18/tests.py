"""Audited tests for Harsh Annotation (collector key 18).

Verifies the Harsh Annotation card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import HarshAnnotation

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestHarshAnnotationBasicProperties:
    """Basic property tests for Harsh Annotation."""

    def test_is_instant(self) -> None:
        """Harsh Annotation must be a Instant subclass."""
        card = HarshAnnotation(name="Harsh Annotation", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """HarshAnnotation.name must be 'Harsh Annotation'."""
        card = HarshAnnotation(name="Harsh Annotation", owner=None)
        assert card.name == "Harsh Annotation"

    def test_card_types(self) -> None:
        """Harsh Annotation must have correct card types."""
        card = HarshAnnotation(name="Harsh Annotation", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Harsh Annotation must have converted mana cost 2."""
        card = HarshAnnotation(name="Harsh Annotation", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Harsh Annotation must have correct colors."""
        card = HarshAnnotation(name="Harsh Annotation", owner=None)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestHarshAnnotationAbilities:
    """Ability tests for Harsh Annotation — expected to fail against stubs."""

    def test_destroys_target_creature(self) -> None:
        """Must destroy the targeted creature."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = HarshAnnotation(name="Harsh Annotation", owner=player)
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

    def test_token_for_destroyed_creatures_controller(self) -> None:
        """Token goes to destroyed creature controller, not caster."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = HarshAnnotation(name="Harsh Annotation", owner=caster)
        card.controller = caster
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        caster_bf = len(game.get_battlefield(caster).get_all())
        assert caster_bf == 0, (
            f"Token must go to destroyed creature controller, not caster (caster bf={caster_bf})"
        )

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = HarshAnnotation(name="Harsh Annotation", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

@pytest.mark.edge
class TestHarshAnnotationEdgeCases:
    """Edge case tests for Harsh Annotation."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = HarshAnnotation(name="Harsh Annotation", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestHarshAnnotationInteractions:
    """Interaction tests for Harsh Annotation."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = HarshAnnotation(name="Harsh Annotation", owner=player)
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
        card = HarshAnnotation(name="Harsh Annotation", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
