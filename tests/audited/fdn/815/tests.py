"""Audited tests for Dictate of Heliod (FDN — synthetic dir 815)."""
from __future__ import annotations
import pytest
from card_impl import DictateOfHeliod
from engine.card import Enchantment, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestDictateOfHeliodBasic:
    def test_is_enchantment(self) -> None:
        card = DictateOfHeliod(name="Dictate of Heliod", owner=None)
        assert isinstance(card, Enchantment)
        assert CardType.ENCHANTMENT in card.card_types
    def test_not_aura(self) -> None:
        card = DictateOfHeliod(name="Dictate of Heliod", owner=None)
        assert not card.is_aura

@pytest.mark.ability
class TestDictateOfHeliodAbility:
    def test_buffs_own_creature_plus2_plus2(self) -> None:
        """Dictate of Heliod gives +2/+2."""
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        ench = DictateOfHeliod(name="Dictate of Heliod", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 4
        assert c.base_toughness == 4

@pytest.mark.edge
class TestDictateOfHeliodEdge:
    def test_does_not_buff_opponent(self) -> None:
        """Only the controller's creatures should be buffed."""
        game = create_game()
        own_c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        opp_c = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[1])
        ench = DictateOfHeliod(name="Dictate of Heliod", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[own_c, ench])
        set_board_state(game, 1, battlefield=[opp_c])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert opp_c.base_power == 3  # unchanged
