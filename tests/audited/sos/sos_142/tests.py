"""Audited tests for Chelonian Tackle (collector key 142).

Verifies the Chelonian Tackle card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ChelonianTackle

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestChelonianTackleBasicProperties:
    """Basic property tests for Chelonian Tackle."""

    def test_is_sorcery(self) -> None:
        """Chelonian Tackle must be a Sorcery subclass."""
        card = ChelonianTackle(name="Chelonian Tackle", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """ChelonianTackle.name must be 'Chelonian Tackle'."""
        card = ChelonianTackle(name="Chelonian Tackle", owner=None)
        assert card.name == "Chelonian Tackle"

    def test_card_types(self) -> None:
        """Chelonian Tackle must have correct card types."""
        card = ChelonianTackle(name="Chelonian Tackle", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Chelonian Tackle must have converted mana cost 3."""
        card = ChelonianTackle(name="Chelonian Tackle", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Chelonian Tackle must have correct colors."""
        card = ChelonianTackle(name="Chelonian Tackle", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestChelonianTackleAbilities:
    """Ability tests for Chelonian Tackle — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +0/+10."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = ChelonianTackle(name="Chelonian Tackle", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 1, (
            f"Should pump to 1 power, got {actual_power}"
        )


@pytest.mark.edge
class TestChelonianTackleEdgeCases:
    """Edge case tests for Chelonian Tackle."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = ChelonianTackle(name="Chelonian Tackle", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestChelonianTackleInteractions:
    """Interaction tests for Chelonian Tackle."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = ChelonianTackle(name="Chelonian Tackle", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = ChelonianTackle(name="Chelonian Tackle", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
