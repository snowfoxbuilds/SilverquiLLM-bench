"""Audited tests for Wander Off (collector key 104).

Verifies the Wander Off card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import WanderOff

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestWanderOffBasicProperties:
    """Basic property tests for Wander Off."""

    def test_is_instant(self) -> None:
        """Wander Off must be a Instant subclass."""
        card = WanderOff(name="Wander Off", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """WanderOff.name must be 'Wander Off'."""
        card = WanderOff(name="Wander Off", owner=None)
        assert card.name == "Wander Off"

    def test_card_types(self) -> None:
        """Wander Off must have correct card types."""
        card = WanderOff(name="Wander Off", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Wander Off must have converted mana cost 4."""
        card = WanderOff(name="Wander Off", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Wander Off must have correct colors."""
        card = WanderOff(name="Wander Off", owner=None)
        assert "B" in card_colors(card)

@pytest.mark.ability
class TestWanderOffAbilities:
    """Ability tests for Wander Off — expected to fail against stubs."""

    def test_exiles_target(self) -> None:
        """Resolution should exile the target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        target = Creature(name="Exiled", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = WanderOff(name="Wander Off", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert target in exile, "Target should be in exile"

@pytest.mark.edge
class TestWanderOffEdgeCases:
    """Edge case tests for Wander Off."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = WanderOff(name="Wander Off", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestWanderOffInteractions:
    """Interaction tests for Wander Off."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = WanderOff(name="Wander Off", owner=player)
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
        card = WanderOff(name="Wander Off", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
