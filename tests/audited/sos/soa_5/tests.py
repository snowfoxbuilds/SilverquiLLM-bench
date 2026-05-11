"""Audited tests for Helping Hand (collector key soa_5).

Verifies the Helping Hand card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import HelpingHand

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestHelpingHandBasicProperties:
    """Basic property tests for Helping Hand."""

    def test_is_sorcery(self) -> None:
        """Helping Hand must be a Sorcery subclass."""
        card = HelpingHand(name="Helping Hand", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """HelpingHand.name must be 'Helping Hand'."""
        card = HelpingHand(name="Helping Hand", owner=None)
        assert card.name == "Helping Hand"

    def test_card_types(self) -> None:
        """Helping Hand must have correct card types."""
        card = HelpingHand(name="Helping Hand", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Helping Hand must have converted mana cost 1."""
        card = HelpingHand(name="Helping Hand", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Helping Hand must have correct colors."""
        card = HelpingHand(name="Helping Hand", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestHelpingHandAbilities:
    """Ability tests for Helping Hand — expected to fail against stubs."""

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = HelpingHand(name="Helping Hand", owner=player)
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
class TestHelpingHandEdgeCases:
    """Edge case tests for Helping Hand."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = HelpingHand(name="Helping Hand", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestHelpingHandInteractions:
    """Interaction tests for Helping Hand."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = HelpingHand(name="Helping Hand", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = HelpingHand(name="Helping Hand", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
