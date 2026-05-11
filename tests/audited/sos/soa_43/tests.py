"""Audited tests for Empty the Warrens (collector key soa_43).

Verifies the Empty the Warrens card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import EmptyTheWarrens

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEmptyTheWarrensBasicProperties:
    """Basic property tests for Empty the Warrens."""

    def test_is_sorcery(self) -> None:
        """Empty the Warrens must be a Sorcery subclass."""
        card = EmptyTheWarrens(name="Empty the Warrens", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """EmptyTheWarrens.name must be 'Empty the Warrens'."""
        card = EmptyTheWarrens(name="Empty the Warrens", owner=None)
        assert card.name == "Empty the Warrens"

    def test_card_types(self) -> None:
        """Empty the Warrens must have correct card types."""
        card = EmptyTheWarrens(name="Empty the Warrens", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Empty the Warrens must have converted mana cost 4."""
        card = EmptyTheWarrens(name="Empty the Warrens", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Empty the Warrens must have correct colors."""
        card = EmptyTheWarrens(name="Empty the Warrens", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestEmptyTheWarrensAbilities:
    """Ability tests for Empty the Warrens — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = EmptyTheWarrens(name="Empty the Warrens", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )


@pytest.mark.edge
class TestEmptyTheWarrensEdgeCases:
    """Edge case tests for Empty the Warrens."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = EmptyTheWarrens(name="Empty the Warrens", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestEmptyTheWarrensInteractions:
    """Interaction tests for Empty the Warrens."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = EmptyTheWarrens(name="Empty the Warrens", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = EmptyTheWarrens(name="Empty the Warrens", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
