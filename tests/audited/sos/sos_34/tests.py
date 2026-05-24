"""Audited tests for Stand Up for Yourself (collector key 34).

Verifies the Stand Up for Yourself card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import StandUpForYourself

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestStandUpForYourselfBasicProperties:
    """Basic property tests for Stand Up for Yourself."""

    def test_is_instant(self) -> None:
        """Stand Up for Yourself must be a Instant subclass."""
        card = StandUpForYourself(name="Stand Up for Yourself", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """StandUpForYourself.name must be 'Stand Up for Yourself'."""
        card = StandUpForYourself(name="Stand Up for Yourself", owner=None)
        assert card.name == "Stand Up for Yourself"

    def test_card_types(self) -> None:
        """Stand Up for Yourself must have correct card types."""
        card = StandUpForYourself(name="Stand Up for Yourself", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Stand Up for Yourself must have converted mana cost 3."""
        card = StandUpForYourself(name="Stand Up for Yourself", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Stand Up for Yourself must have correct colors."""
        card = StandUpForYourself(name="Stand Up for Yourself", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestStandUpForYourselfAbilities:
    """Ability tests for Stand Up for Yourself — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = StandUpForYourself(name="Stand Up for Yourself", owner=player)
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
class TestStandUpForYourselfEdgeCases:
    """Edge case tests for Stand Up for Yourself."""

    def test_power_targeting_restriction(self) -> None:
        """Only targets creatures with power 3 or greater."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        small = Creature(name="Small", owner=opponent, base_power=2, base_toughness=2)
        big = Creature(name="Big", owner=opponent, base_power=3, base_toughness=2)
        set_board_state(game, 1, battlefield=[small, big])
        card = StandUpForYourself(name="Stand Up for Yourself", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert big in targets, "Power >= 3 should be valid"
        assert small not in targets, "Power < 3 should be invalid"


@pytest.mark.interaction
class TestStandUpForYourselfInteractions:
    """Interaction tests for Stand Up for Yourself."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = StandUpForYourself(name="Stand Up for Yourself", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = StandUpForYourself(name="Stand Up for Yourself", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
