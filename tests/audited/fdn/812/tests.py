"""Audited tests for Stab Wound (FDN — synthetic dir 812)."""
from __future__ import annotations
import pytest
from card_impl import StabWound
from engine.card import Aura, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestStabWoundBasic:
    def test_is_aura(self) -> None:
        assert isinstance(StabWound(name="Stab Wound", owner=None), Aura)

@pytest.mark.ability
class TestStabWoundAbility:
    def test_reduces_power(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=4, base_toughness=4, owner=game.players[0])
        a = StabWound(name="Stab Wound", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power <= 2
    def test_reduces_toughness(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=4, base_toughness=4, owner=game.players[0])
        a = StabWound(name="Stab Wound", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_toughness <= 2
