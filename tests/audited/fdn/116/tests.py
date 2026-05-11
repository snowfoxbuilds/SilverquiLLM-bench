"""Audited tests for Anthem of Champions (FDN collector number 116)."""
from __future__ import annotations
import pytest
from card_impl import AnthemOfChampions
from engine.card import Enchantment, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestAnthemOfChampionsBasic:
    def test_is_enchantment(self) -> None:
        card = AnthemOfChampions(name="Anthem of Champions", owner=None)
        assert isinstance(card, Enchantment)
        assert CardType.ENCHANTMENT in card.card_types
    def test_not_aura(self) -> None:
        card = AnthemOfChampions(name="Anthem of Champions", owner=None)
        assert not card.is_aura

@pytest.mark.ability
class TestAnthemOfChampionsAbility:
    def test_buffs_power_by_one(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        ench = AnthemOfChampions(name="Anthem of Champions", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 3
    def test_buffs_toughness_by_one(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        ench = AnthemOfChampions(name="Anthem of Champions", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_toughness == 3
    def test_buffs_all_own_creatures(self) -> None:
        """All creatures you control get the buff."""
        game = create_game()
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[0])
        ench = AnthemOfChampions(name="Anthem of Champions", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c1, c2, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.base_power == 3
        assert c2.base_power == 4

@pytest.mark.edge
class TestAnthemOfChampionsEdge:
    def test_does_not_affect_opponent(self) -> None:
        """Anthem only affects your creatures."""
        game = create_game()
        own_c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        opp_c = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[1])
        ench = AnthemOfChampions(name="Anthem of Champions", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[own_c, ench])
        set_board_state(game, 1, battlefield=[opp_c])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert opp_c.base_power == 3
