"""Audited tests for Garruk's Uprising (FDN collector number 220)."""
from __future__ import annotations
import pytest
from card_impl import GarruksUprising
from engine.card import Enchantment, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestGarruksUprisingBasic:
    def test_is_enchantment(self) -> None:
        assert isinstance(GarruksUprising(name="Garruk\'s Uprising", owner=None), Enchantment)

@pytest.mark.ability
class TestGarruksUprisingAbility:
    def test_grants_trample(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        ench = GarruksUprising(name="Garruk\'s Uprising", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.TRAMPLE in c.keywords
