"""Audited tests for Brave the Sands (FDN — synthetic dir 816)."""
from __future__ import annotations
import pytest
from card_impl import BraveTheSands
from engine.card import Enchantment, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestBraveTheSandsBasic:
    def test_is_enchantment(self) -> None:
        assert isinstance(BraveTheSands(name="Brave the Sands", owner=None), Enchantment)

@pytest.mark.ability
class TestBraveTheSandsAbility:
    def test_grants_vigilance(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        ench = BraveTheSands(name="Brave the Sands", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.VIGILANCE in c.keywords
