"""Audited tests for Fracture (collector key soa_65).

Verifies the Fracture card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Fracture

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestFractureBasicProperties:
    """Basic property tests for Fracture."""

    def test_is_instant(self) -> None:
        """Fracture must be a Instant subclass."""
        card = Fracture(name="Fracture", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Fracture.name must be 'Fracture'."""
        card = Fracture(name="Fracture", owner=None)
        assert card.name == "Fracture"

    def test_card_types(self) -> None:
        """Fracture must have correct card types."""
        card = Fracture(name="Fracture", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Fracture must have converted mana cost 2."""
        card = Fracture(name="Fracture", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Fracture must have correct colors."""
        card = Fracture(name="Fracture", owner=None)
        assert "B" in card.colors
        assert "W" in card.colors


@pytest.mark.ability
class TestFractureAbilities:
    """Ability tests for Fracture — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = Fracture(name="Fracture", owner=player)
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
class TestFractureEdgeCases:
    """Edge case tests for Fracture."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Fracture(name="Fracture", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestFractureInteractions:
    """Interaction tests for Fracture."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = Fracture(name="Fracture", owner=player)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = Fracture(name="Fracture", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
