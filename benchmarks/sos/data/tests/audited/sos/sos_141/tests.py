"""Audited tests for Burrog Barrage (collector key 141).

Verifies the Burrog Barrage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import BurrogBarrage

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestBurrogBarrageBasicProperties:
    """Basic property tests for Burrog Barrage."""

    def test_is_instant(self) -> None:
        """Burrog Barrage must be a Instant subclass."""
        card = BurrogBarrage(name="Burrog Barrage", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """BurrogBarrage.name must be 'Burrog Barrage'."""
        card = BurrogBarrage(name="Burrog Barrage", owner=None)
        assert card.name == "Burrog Barrage"

    def test_card_types(self) -> None:
        """Burrog Barrage must have correct card types."""
        card = BurrogBarrage(name="Burrog Barrage", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Burrog Barrage must have converted mana cost 2."""
        card = BurrogBarrage(name="Burrog Barrage", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Burrog Barrage must have correct colors."""
        card = BurrogBarrage(name="Burrog Barrage", owner=None)
        assert "G" in card_colors(card)

@pytest.mark.ability
class TestBurrogBarrageAbilities:
    """Ability tests for Burrog Barrage — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +1/+0."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = BurrogBarrage(name="Burrog Barrage", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 2, (
            f"Should pump to 2 power, got {actual_power}"
        )

@pytest.mark.edge
class TestBurrogBarrageEdgeCases:
    """Edge case tests for Burrog Barrage."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = BurrogBarrage(name="Burrog Barrage", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"

@pytest.mark.interaction
class TestBurrogBarrageInteractions:
    """Interaction tests for Burrog Barrage."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = BurrogBarrage(name="Burrog Barrage", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = BurrogBarrage(name="Burrog Barrage", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
