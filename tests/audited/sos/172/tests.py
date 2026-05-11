"""Audited tests for Applied Geometry (collector key 172).

Verifies the Applied Geometry card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import AppliedGeometry

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestAppliedGeometryBasicProperties:
    """Basic property tests for Applied Geometry."""

    def test_is_sorcery(self) -> None:
        """Applied Geometry must be a Sorcery subclass."""
        card = AppliedGeometry(name="Applied Geometry", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """AppliedGeometry.name must be 'Applied Geometry'."""
        card = AppliedGeometry(name="Applied Geometry", owner=None)
        assert card.name == "Applied Geometry"

    def test_card_types(self) -> None:
        """Applied Geometry must have correct card types."""
        card = AppliedGeometry(name="Applied Geometry", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Applied Geometry must have converted mana cost 4."""
        card = AppliedGeometry(name="Applied Geometry", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Applied Geometry must have correct colors."""
        card = AppliedGeometry(name="Applied Geometry", owner=None)
        assert "G" in card.colors
        assert "U" in card.colors


@pytest.mark.ability
class TestAppliedGeometryAbilities:
    """Ability tests for Applied Geometry — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = AppliedGeometry(name="Applied Geometry", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = AppliedGeometry(name="Applied Geometry", owner=player)
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
class TestAppliedGeometryEdgeCases:
    """Edge case tests for Applied Geometry."""

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
        card = AppliedGeometry(name="Applied Geometry", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestAppliedGeometryInteractions:
    """Interaction tests for Applied Geometry."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = AppliedGeometry(name="Applied Geometry", owner=player)
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
        card = AppliedGeometry(name="Applied Geometry", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
