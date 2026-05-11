"""Audited tests for Unholy Strength (FDN — synthetic dir 811)."""
from __future__ import annotations
import pytest
from card_impl import UnholyStrength
from engine.card import Aura, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestUnholyStrengthBasic:
    def test_is_aura(self) -> None:
        assert isinstance(UnholyStrength(name="Unholy Strength", owner=None), Aura)

@pytest.mark.ability
class TestUnholyStrengthAbility:
    def test_power_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UnholyStrength(name="Unholy Strength", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power >= 4
    def test_toughness_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UnholyStrength(name="Unholy Strength", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_toughness >= 3
