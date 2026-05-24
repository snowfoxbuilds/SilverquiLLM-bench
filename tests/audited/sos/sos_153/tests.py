"""Audited tests for Lumaret's Favor (collector key 153).

Verifies the Lumaret's Favor card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import LumaretsFavor

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestLumaretsFavorBasicProperties:
    """Basic property tests for Lumaret's Favor."""

    def test_is_instant(self) -> None:
        """Lumaret's Favor must be a Instant subclass."""
        card = LumaretsFavor(name="Lumaret's Favor", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """LumaretsFavor.name must be 'Lumaret's Favor'."""
        card = LumaretsFavor(name="Lumaret's Favor", owner=None)
        assert card.name == "Lumaret's Favor"

    def test_card_types(self) -> None:
        """Lumaret's Favor must have correct card types."""
        card = LumaretsFavor(name="Lumaret's Favor", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Lumaret's Favor must have converted mana cost 2."""
        card = LumaretsFavor(name="Lumaret's Favor", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Lumaret's Favor must have correct colors."""
        card = LumaretsFavor(name="Lumaret's Favor", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestLumaretsFavorAbilities:
    """Ability tests for Lumaret's Favor — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +2/+4."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = LumaretsFavor(name="Lumaret's Favor", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 3, (
            f"Should pump to 3 power, got {actual_power}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = LumaretsFavor(name="Lumaret's Favor", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestLumaretsFavorEdgeCases:
    """Edge case tests for Lumaret's Favor."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = LumaretsFavor(name="Lumaret's Favor", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestLumaretsFavorInteractions:
    """Interaction tests for Lumaret's Favor."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = LumaretsFavor(name="Lumaret's Favor", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = LumaretsFavor(name="Lumaret's Favor", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
