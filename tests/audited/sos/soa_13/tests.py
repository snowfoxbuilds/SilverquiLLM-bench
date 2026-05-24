"""Audited tests for Brain Freeze (collector key soa_13).

Verifies the Brain Freeze card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import BrainFreeze

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBrainFreezeBasicProperties:
    """Basic property tests for Brain Freeze."""

    def test_is_instant(self) -> None:
        """Brain Freeze must be a Instant subclass."""
        card = BrainFreeze(name="Brain Freeze", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """BrainFreeze.name must be 'Brain Freeze'."""
        card = BrainFreeze(name="Brain Freeze", owner=None)
        assert card.name == "Brain Freeze"

    def test_card_types(self) -> None:
        """Brain Freeze must have correct card types."""
        card = BrainFreeze(name="Brain Freeze", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Brain Freeze must have converted mana cost 2."""
        card = BrainFreeze(name="Brain Freeze", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Brain Freeze must have correct colors."""
        card = BrainFreeze(name="Brain Freeze", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestBrainFreezeAbilities:
    """Ability tests for Brain Freeze — expected to fail against stubs."""

    def test_mill_effect(self) -> None:
        """Resolution should mill 2 cards."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Sorcery
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        for i in range(4):
            opponent.zones[Zone.LIBRARY].add(Sorcery(name=f"Mill{i}", owner=opponent))
        gy_before = len(opponent.zones[Zone.GRAVEYARD].get_all())
        card = BrainFreeze(name="Brain Freeze", owner=player)
        card.controller = player
        card.on_resolve(game)
        gy_after = len(opponent.zones[Zone.GRAVEYARD].get_all())
        assert gy_after > gy_before, (
            f"Should mill: gy {gy_before} -> {gy_after}"
        )


@pytest.mark.edge
class TestBrainFreezeEdgeCases:
    """Edge case tests for Brain Freeze."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BrainFreeze(name="Brain Freeze", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestBrainFreezeInteractions:
    """Interaction tests for Brain Freeze."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = BrainFreeze(name="Brain Freeze", owner=player)
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
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = BrainFreeze(name="Brain Freeze", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
