"""Audited tests for Grapple with Death (collector key 192).

Verifies the Grapple with Death card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import GrappleWithDeath

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestGrappleWithDeathBasicProperties:
    """Basic property tests for Grapple with Death."""

    def test_is_sorcery(self) -> None:
        """Grapple with Death must be a Sorcery subclass."""
        card = GrappleWithDeath(name="Grapple with Death", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """GrappleWithDeath.name must be 'Grapple with Death'."""
        card = GrappleWithDeath(name="Grapple with Death", owner=None)
        assert card.name == "Grapple with Death"

    def test_card_types(self) -> None:
        """Grapple with Death must have correct card types."""
        card = GrappleWithDeath(name="Grapple with Death", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Grapple with Death must have converted mana cost 3."""
        card = GrappleWithDeath(name="Grapple with Death", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Grapple with Death must have correct colors."""
        card = GrappleWithDeath(name="Grapple with Death", owner=None)
        assert "B" in card_colors(card)
        assert "G" in card_colors(card)

@pytest.mark.ability
class TestGrappleWithDeathAbilities:
    """Ability tests for Grapple with Death — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = GrappleWithDeath(name="Grapple with Death", owner=player)
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

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GrappleWithDeath(name="Grapple with Death", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

@pytest.mark.edge
class TestGrappleWithDeathEdgeCases:
    """Edge case tests for Grapple with Death."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GrappleWithDeath(name="Grapple with Death", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestGrappleWithDeathInteractions:
    """Interaction tests for Grapple with Death."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = GrappleWithDeath(name="Grapple with Death", owner=player)
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
        card = GrappleWithDeath(name="Grapple with Death", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
