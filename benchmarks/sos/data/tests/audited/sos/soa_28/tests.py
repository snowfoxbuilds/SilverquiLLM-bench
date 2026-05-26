"""Audited tests for Dismember (collector key soa_28).

Verifies the Dismember card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import Dismember

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestDismemberBasicProperties:
    """Basic property tests for Dismember."""

    def test_is_instant(self) -> None:
        """Dismember must be a Instant subclass."""
        card = Dismember(name="Dismember", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Dismember.name must be 'Dismember'."""
        card = Dismember(name="Dismember", owner=None)
        assert card.name == "Dismember"

    def test_card_types(self) -> None:
        """Dismember must have correct card types."""
        card = Dismember(name="Dismember", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Dismember must have converted mana cost 3."""
        card = Dismember(name="Dismember", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Dismember must have correct colors."""
        card = Dismember(name="Dismember", owner=None)
        assert "B" in card_colors(card)

@pytest.mark.ability
class TestDismemberAbilities:
    """Ability tests for Dismember — expected to fail against stubs."""

    def test_on_resolve_changes_state(self) -> None:
        """Resolution must produce observable state change."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = Dismember(name="Dismember", owner=player)
        card.controller = player
        p_life = player.life
        o_life = opponent.life
        p_bf = len(game.get_battlefield(player).get_all())
        o_bf = len(game.get_battlefield(opponent).get_all())
        p_hand = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        changed = (
            player.life != p_life or opponent.life != o_life or
            len(game.get_battlefield(player).get_all()) != p_bf or
            len(game.get_battlefield(opponent).get_all()) != o_bf or
            len(player.zones[Zone.HAND].get_all()) != p_hand or
            len(player.zones[Zone.GRAVEYARD].get_all()) > 0 or
            len(opponent.zones[Zone.GRAVEYARD].get_all()) > 0
        )
        assert changed, "on_resolve must change game state"

@pytest.mark.edge
class TestDismemberEdgeCases:
    """Edge case tests for Dismember."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Dismember(name="Dismember", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestDismemberInteractions:
    """Interaction tests for Dismember."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = Dismember(name="Dismember", owner=player)
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
        card = Dismember(name="Dismember", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
