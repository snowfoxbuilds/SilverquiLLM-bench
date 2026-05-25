"""Audited tests for Erode (collector key 15).

Verifies the Erode card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Erode

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestErodeBasicProperties:
    """Basic property tests for Erode."""

    def test_is_instant(self) -> None:
        """Erode must be a Instant subclass."""
        card = Erode(name="Erode", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Erode.name must be 'Erode'."""
        card = Erode(name="Erode", owner=None)
        assert card.name == "Erode"

    def test_card_types(self) -> None:
        """Erode must have correct card types."""
        card = Erode(name="Erode", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Erode must have converted mana cost 1."""
        card = Erode(name="Erode", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Erode must have correct colors."""
        card = Erode(name="Erode", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestErodeAbilities:
    """Ability tests for Erode — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = Erode(name="Erode", owner=player)
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


@pytest.mark.edge
class TestErodeEdgeCases:
    """Edge case tests for Erode."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Erode(name="Erode", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestErodeInteractions:
    """Interaction tests for Erode."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = Erode(name="Erode", owner=player)
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
        card = Erode(name="Erode", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
