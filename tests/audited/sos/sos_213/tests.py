"""Audited tests for Proctor's Gaze (collector key 213).

Verifies the Proctor's Gaze card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ProctorsGaze

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestProctorsGazeBasicProperties:
    """Basic property tests for Proctor's Gaze."""

    def test_is_instant(self) -> None:
        """Proctor's Gaze must be a Instant subclass."""
        card = ProctorsGaze(name="Proctor's Gaze", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """ProctorsGaze.name must be 'Proctor's Gaze'."""
        card = ProctorsGaze(name="Proctor's Gaze", owner=None)
        assert card.name == "Proctor's Gaze"

    def test_card_types(self) -> None:
        """Proctor's Gaze must have correct card types."""
        card = ProctorsGaze(name="Proctor's Gaze", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Proctor's Gaze must have converted mana cost 4."""
        card = ProctorsGaze(name="Proctor's Gaze", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Proctor's Gaze must have correct colors."""
        card = ProctorsGaze(name="Proctor's Gaze", owner=None)
        assert "G" in card.colors
        assert "U" in card.colors


@pytest.mark.ability
class TestProctorsGazeAbilities:
    """Ability tests for Proctor's Gaze — expected to fail against stubs."""

    def test_bounces_target(self) -> None:
        """Resolution should return target to hand."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Bounced", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = ProctorsGaze(name="Proctor's Gaze", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        bf_before = len(game.get_battlefield(opponent).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(opponent).get_all())
        assert bf_after < bf_before, (
            f"Target should leave bf: {bf_before} -> {bf_after}"
        )

    def test_search_library(self) -> None:
        """Resolution should search library."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(5):
            player.zones[Zone.LIBRARY].add(Sorcery(name=f"Lib{i}", owner=player))
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = ProctorsGaze(name="Proctor's Gaze", owner=player)
        card.controller = player
        card.on_resolve(game)
        lib_after = len(player.zones[Zone.LIBRARY].get_all())
        assert lib_after < lib_before, (
            f"Should search library: {lib_before} -> {lib_after}"
        )


@pytest.mark.edge
class TestProctorsGazeEdgeCases:
    """Edge case tests for Proctor's Gaze."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ProctorsGaze(name="Proctor's Gaze", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestProctorsGazeInteractions:
    """Interaction tests for Proctor's Gaze."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = ProctorsGaze(name="Proctor's Gaze", owner=player)
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
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = ProctorsGaze(name="Proctor's Gaze", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
