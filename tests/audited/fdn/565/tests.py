"""Audited tests for Angelic Destiny (FDN collector number 565)."""
from __future__ import annotations
import pytest
from card_impl import AngelicDestiny
from engine.card import Aura, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestAngelicDestinyBasic:
    def test_is_aura(self) -> None:
        assert isinstance(AngelicDestiny(name="Angelic Destiny", owner=None), Aura)

@pytest.mark.ability
class TestAngelicDestinyAbility:
    def test_power_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = AngelicDestiny(name="Angelic Destiny", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power >= 6
    def test_flying(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = AngelicDestiny(name="Angelic Destiny", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in c.keywords
    def test_first_strike(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        a = AngelicDestiny(name="Angelic Destiny", owner=game.players[0])
        a.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, a])
        a.chosen_targets = [c]; a.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.FIRST_STRIKE in c.keywords
