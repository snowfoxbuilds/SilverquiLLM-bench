"""Audited tests for Ajani's Response (collector key 6).

Verifies the Ajani's Response card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import AjanisResponse

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestAjanisResponseBasicProperties:
    """Basic property tests for Ajani's Response."""

    def test_is_instant(self) -> None:
        """Ajani's Response must be a Instant subclass."""
        card = AjanisResponse(name="Ajani's Response", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """AjanisResponse.name must be 'Ajani's Response'."""
        card = AjanisResponse(name="Ajani's Response", owner=None)
        assert card.name == "Ajani's Response"

    def test_card_types(self) -> None:
        """Ajani's Response must have correct card types."""
        card = AjanisResponse(name="Ajani's Response", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ajani's Response must have converted mana cost 5."""
        card = AjanisResponse(name="Ajani's Response", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Ajani's Response must have correct colors."""
        card = AjanisResponse(name="Ajani's Response", owner=None)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestAjanisResponseAbilities:
    """Ability tests for Ajani's Response — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = AjanisResponse(name="Ajani's Response", owner=player)
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

    def test_cost_reduction_applies(self) -> None:
        """cost_reduction should return > 0 when condition met."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = AjanisResponse(name="Ajani's Response", owner=player)
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
class TestAjanisResponseEdgeCases:
    """Edge case tests for Ajani's Response."""

    def test_no_reduction_when_condition_unmet(self) -> None:
        """No cost reduction when condition is not met."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = AjanisResponse(name="Ajani's Response", owner=player)
        card.controller = player
        target = Creature(name="Untapped", owner=player, base_power=2, base_toughness=2)
        target.tapped = False
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        reduction = card.cost_reduction(game)
        assert reduction == 0, f"No reduction when unmet, got {reduction}"

@pytest.mark.interaction
class TestAjanisResponseInteractions:
    """Interaction tests for Ajani's Response."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = AjanisResponse(name="Ajani's Response", owner=player)
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
        card = AjanisResponse(name="Ajani's Response", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
