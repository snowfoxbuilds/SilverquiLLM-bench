"""Audited tests for Royal Treatment (collector key soa_56).

Verifies the Royal Treatment card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import RoyalTreatment

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRoyalTreatmentBasicProperties:
    """Basic property tests for Royal Treatment."""

    def test_is_instant(self) -> None:
        """Royal Treatment must be a Instant subclass."""
        card = RoyalTreatment(name="Royal Treatment", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """RoyalTreatment.name must be 'Royal Treatment'."""
        card = RoyalTreatment(name="Royal Treatment", owner=None)
        assert card.name == "Royal Treatment"

    def test_card_types(self) -> None:
        """Royal Treatment must have correct card types."""
        card = RoyalTreatment(name="Royal Treatment", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Royal Treatment must have converted mana cost 1."""
        card = RoyalTreatment(name="Royal Treatment", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Royal Treatment must have correct colors."""
        card = RoyalTreatment(name="Royal Treatment", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestRoyalTreatmentAbilities:
    """Ability tests for Royal Treatment — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = RoyalTreatment(name="Royal Treatment", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_pump_effect(self) -> None:
        """Resolution should grant +1/+1."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = RoyalTreatment(name="Royal Treatment", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 2, (
            f"Should pump to 2 power, got {actual_power}"
        )

    def test_grants_hexproof(self) -> None:
        """Resolution should grant hexproof."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = RoyalTreatment(name="Royal Treatment", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.HEXPROOF in target.keywords, (
            "Target should have hexproof after resolution"
        )


@pytest.mark.edge
class TestRoyalTreatmentEdgeCases:
    """Edge case tests for Royal Treatment."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = RoyalTreatment(name="Royal Treatment", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestRoyalTreatmentInteractions:
    """Interaction tests for Royal Treatment."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = RoyalTreatment(name="Royal Treatment", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = RoyalTreatment(name="Royal Treatment", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
