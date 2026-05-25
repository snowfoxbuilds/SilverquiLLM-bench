"""Audited tests for Impractical Joke (collector key 119).

Verifies the Impractical Joke card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ImpracticalJoke

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestImpracticalJokeBasicProperties:
    """Basic property tests for Impractical Joke."""

    def test_is_sorcery(self) -> None:
        """Impractical Joke must be a Sorcery subclass."""
        card = ImpracticalJoke(name="Impractical Joke", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """ImpracticalJoke.name must be 'Impractical Joke'."""
        card = ImpracticalJoke(name="Impractical Joke", owner=None)
        assert card.name == "Impractical Joke"

    def test_card_types(self) -> None:
        """Impractical Joke must have correct card types."""
        card = ImpracticalJoke(name="Impractical Joke", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Impractical Joke must have converted mana cost 1."""
        card = ImpracticalJoke(name="Impractical Joke", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Impractical Joke must have correct colors."""
        card = ImpracticalJoke(name="Impractical Joke", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestImpracticalJokeAbilities:
    """Ability tests for Impractical Joke — expected to fail against stubs."""

    def test_deals_damage(self) -> None:
        """Resolution should deal 3 damage."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = ImpracticalJoke(name="Impractical Joke", owner=player)
        card.controller = player
        card._targets = [opponent]
        if hasattr(card, "set_targets"):
            card.set_targets([opponent])
        card.on_resolve(game)
        life_after = opponent.life
        assert life_after < life_before, (
            f"Should deal damage: life {life_before} -> {life_after}"
        )


@pytest.mark.edge
class TestImpracticalJokeEdgeCases:
    """Edge case tests for Impractical Joke."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ImpracticalJoke(name="Impractical Joke", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestImpracticalJokeInteractions:
    """Interaction tests for Impractical Joke."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = ImpracticalJoke(name="Impractical Joke", owner=player)
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
        card = ImpracticalJoke(name="Impractical Joke", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
