"""Audited tests for Knockout Maneuver (collector key soa_54).

Verifies the Knockout Maneuver card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import KnockoutManeuver

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestKnockoutManeuverBasicProperties:
    """Basic property tests for Knockout Maneuver."""

    def test_is_sorcery(self) -> None:
        """Knockout Maneuver must be a Sorcery subclass."""
        card = KnockoutManeuver(name="Knockout Maneuver", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """KnockoutManeuver.name must be 'Knockout Maneuver'."""
        card = KnockoutManeuver(name="Knockout Maneuver", owner=None)
        assert card.name == "Knockout Maneuver"

    def test_card_types(self) -> None:
        """Knockout Maneuver must have correct card types."""
        card = KnockoutManeuver(name="Knockout Maneuver", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Knockout Maneuver must have converted mana cost 3."""
        card = KnockoutManeuver(name="Knockout Maneuver", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Knockout Maneuver must have correct colors."""
        card = KnockoutManeuver(name="Knockout Maneuver", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestKnockoutManeuverAbilities:
    """Ability tests for Knockout Maneuver — expected to fail against stubs."""

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = KnockoutManeuver(name="Knockout Maneuver", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        power_before = target.base_power
        card.on_resolve(game)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"+1/+1 counter: power {power_before} -> {power_after}"
        )


@pytest.mark.edge
class TestKnockoutManeuverEdgeCases:
    """Edge case tests for Knockout Maneuver."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = KnockoutManeuver(name="Knockout Maneuver", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestKnockoutManeuverInteractions:
    """Interaction tests for Knockout Maneuver."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = KnockoutManeuver(name="Knockout Maneuver", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = KnockoutManeuver(name="Knockout Maneuver", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
