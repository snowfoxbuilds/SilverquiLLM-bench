"""Audited tests for Comforting Counsel (collector key 143).

Verifies the Comforting Counsel card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ComfortingCounsel

from engine.card import Enchantment
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestComfortingCounselBasicProperties:
    """Basic property tests for Comforting Counsel."""

    def test_is_enchantment(self) -> None:
        """Comforting Counsel must be a Enchantment subclass."""
        card = ComfortingCounsel(name="Comforting Counsel", owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        """ComfortingCounsel.name must be 'Comforting Counsel'."""
        card = ComfortingCounsel(name="Comforting Counsel", owner=None)
        assert card.name == "Comforting Counsel"

    def test_card_types(self) -> None:
        """Comforting Counsel must have correct card types."""
        card = ComfortingCounsel(name="Comforting Counsel", owner=None)
        assert CardType.ENCHANTMENT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Comforting Counsel must have converted mana cost 2."""
        card = ComfortingCounsel(name="Comforting Counsel", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Comforting Counsel must have correct colors."""
        card = ComfortingCounsel(name="Comforting Counsel", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestComfortingCounselAbilities:
    """Ability tests for Comforting Counsel — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +3/+3."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = ComfortingCounsel(name="Comforting Counsel", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 4, (
            f"Should pump to 4 power, got {actual_power}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ComfortingCounsel(name="Comforting Counsel", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestComfortingCounselEdgeCases:
    """Edge case tests for Comforting Counsel."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ComfortingCounsel(name="Comforting Counsel", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestComfortingCounselInteractions:
    """Interaction tests for Comforting Counsel."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = ComfortingCounsel(name="Comforting Counsel", owner=player)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = ComfortingCounsel(name="Comforting Counsel", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
