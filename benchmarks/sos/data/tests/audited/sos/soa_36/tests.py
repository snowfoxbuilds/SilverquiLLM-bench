"""Audited tests for Zombify (collector key soa_36).

Verifies the Zombify card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Zombify

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestZombifyBasicProperties:
    """Basic property tests for Zombify."""

    def test_is_sorcery(self) -> None:
        """Zombify must be a Sorcery subclass."""
        card = Zombify(name="Zombify", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """Zombify.name must be 'Zombify'."""
        card = Zombify(name="Zombify", owner=None)
        assert card.name == "Zombify"

    def test_card_types(self) -> None:
        """Zombify must have correct card types."""
        card = Zombify(name="Zombify", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Zombify must have converted mana cost 4."""
        card = Zombify(name="Zombify", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Zombify must have correct colors."""
        card = Zombify(name="Zombify", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestZombifyAbilities:
    """Ability tests for Zombify — expected to fail against stubs."""

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = Zombify(name="Zombify", owner=player)
        card.controller = player
        card._targets = [gy_card]
        if hasattr(card, "set_targets"):
            card.set_targets([gy_card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after < gy_before, (
            f"Should return from gy: {gy_before} -> {gy_after}"
        )


@pytest.mark.edge
class TestZombifyEdgeCases:
    """Edge case tests for Zombify."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Zombify(name="Zombify", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestZombifyInteractions:
    """Interaction tests for Zombify."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = Zombify(name="Zombify", owner=player)
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
        card = Zombify(name="Zombify", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
