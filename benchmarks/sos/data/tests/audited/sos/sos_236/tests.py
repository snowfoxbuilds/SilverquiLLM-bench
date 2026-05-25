"""Audited tests for Suspend Aggression (collector key 236).

Verifies the Suspend Aggression card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SuspendAggression

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSuspendAggressionBasicProperties:
    """Basic property tests for Suspend Aggression."""

    def test_is_instant(self) -> None:
        """Suspend Aggression must be a Instant subclass."""
        card = SuspendAggression(name="Suspend Aggression", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """SuspendAggression.name must be 'Suspend Aggression'."""
        card = SuspendAggression(name="Suspend Aggression", owner=None)
        assert card.name == "Suspend Aggression"

    def test_card_types(self) -> None:
        """Suspend Aggression must have correct card types."""
        card = SuspendAggression(name="Suspend Aggression", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Suspend Aggression must have converted mana cost 3."""
        card = SuspendAggression(name="Suspend Aggression", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Suspend Aggression must have correct colors."""
        card = SuspendAggression(name="Suspend Aggression", owner=None)
        assert "R" in card.colors
        assert "W" in card.colors


@pytest.mark.ability
class TestSuspendAggressionAbilities:
    """Ability tests for Suspend Aggression — expected to fail against stubs."""

    def test_exiles_target(self) -> None:
        """Resolution should exile the target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        target = Creature(name="Exiled", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = SuspendAggression(name="Suspend Aggression", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert target in exile, "Target should be in exile"


@pytest.mark.edge
class TestSuspendAggressionEdgeCases:
    """Edge case tests for Suspend Aggression."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SuspendAggression(name="Suspend Aggression", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestSuspendAggressionInteractions:
    """Interaction tests for Suspend Aggression."""

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
        card = SuspendAggression(name="Suspend Aggression", owner=player)
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
        card = SuspendAggression(name="Suspend Aggression", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
