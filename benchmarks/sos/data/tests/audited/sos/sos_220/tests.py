"""Audited tests for Render Speechless (collector key 220).

Verifies the Render Speechless card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import RenderSpeechless

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRenderSpeechlessBasicProperties:
    """Basic property tests for Render Speechless."""

    def test_is_sorcery(self) -> None:
        """Render Speechless must be a Sorcery subclass."""
        card = RenderSpeechless(name="Render Speechless", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """RenderSpeechless.name must be 'Render Speechless'."""
        card = RenderSpeechless(name="Render Speechless", owner=None)
        assert card.name == "Render Speechless"

    def test_card_types(self) -> None:
        """Render Speechless must have correct card types."""
        card = RenderSpeechless(name="Render Speechless", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Render Speechless must have converted mana cost 4."""
        card = RenderSpeechless(name="Render Speechless", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Render Speechless must have correct colors."""
        card = RenderSpeechless(name="Render Speechless", owner=None)
        assert "B" in card.colors
        assert "W" in card.colors


@pytest.mark.ability
class TestRenderSpeechlessAbilities:
    """Ability tests for Render Speechless — expected to fail against stubs."""

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = RenderSpeechless(name="Render Speechless", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        power_before = target.base_power
        card.on_resolve(game)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"+1/+1 counter: power {power_before} -> {power_after}"
        )

    def test_causes_discard(self) -> None:
        """Resolution should cause discard."""
        from test_utils import create_game, set_board_state
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        filler = Sorcery(name="Discardable", owner=opponent)
        set_board_state(game, 1, hand=[filler])
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = RenderSpeechless(name="Render Speechless", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )


@pytest.mark.edge
class TestRenderSpeechlessEdgeCases:
    """Edge case tests for Render Speechless."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = RenderSpeechless(name="Render Speechless", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestRenderSpeechlessInteractions:
    """Interaction tests for Render Speechless."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = RenderSpeechless(name="Render Speechless", owner=player)
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
        card = RenderSpeechless(name="Render Speechless", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
