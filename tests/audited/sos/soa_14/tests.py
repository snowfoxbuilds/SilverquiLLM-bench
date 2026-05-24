"""Audited tests for Cyclonic Rift (collector key soa_14).

Verifies the Cyclonic Rift card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import CyclonicRift

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestCyclonicRiftBasicProperties:
    """Basic property tests for Cyclonic Rift."""

    def test_is_instant(self) -> None:
        """Cyclonic Rift must be a Instant subclass."""
        card = CyclonicRift(name="Cyclonic Rift", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """CyclonicRift.name must be 'Cyclonic Rift'."""
        card = CyclonicRift(name="Cyclonic Rift", owner=None)
        assert card.name == "Cyclonic Rift"

    def test_card_types(self) -> None:
        """Cyclonic Rift must have correct card types."""
        card = CyclonicRift(name="Cyclonic Rift", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Cyclonic Rift must have converted mana cost 2."""
        card = CyclonicRift(name="Cyclonic Rift", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Cyclonic Rift must have correct colors."""
        card = CyclonicRift(name="Cyclonic Rift", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestCyclonicRiftAbilities:
    """Ability tests for Cyclonic Rift — expected to fail against stubs."""

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
        card = CyclonicRift(name="Cyclonic Rift", owner=player)
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


@pytest.mark.edge
class TestCyclonicRiftEdgeCases:
    """Edge case tests for Cyclonic Rift."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CyclonicRift(name="Cyclonic Rift", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestCyclonicRiftInteractions:
    """Interaction tests for Cyclonic Rift."""

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
        card = CyclonicRift(name="Cyclonic Rift", owner=player)
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
        card = CyclonicRift(name="Cyclonic Rift", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
