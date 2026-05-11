"""Audited tests for Untamed Hunger (FDN collector number 529)."""
from __future__ import annotations
import pytest
from card_impl import UntamedHunger
from engine.card import Aura, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestUntamedHungerBasic:
    def test_is_aura(self) -> None:
        assert isinstance(UntamedHunger(name="Untamed Hunger", owner=None), Aura)

@pytest.mark.ability
class TestUntamedHungerAbility:
    def test_power_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UntamedHunger(name="Untamed Hunger", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power >= 4
    def test_toughness_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UntamedHunger(name="Untamed Hunger", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_toughness >= 3
    def test_menace(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = UntamedHunger(name="Untamed Hunger", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.MENACE in c.keywords
