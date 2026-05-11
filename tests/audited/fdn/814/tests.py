"""Audited tests for Glorious Anthem (FDN — synthetic dir 814)."""
from __future__ import annotations
import pytest
from card_impl import GloriousAnthem
from engine.card import Enchantment, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestGloriousAnthemBasic:
    def test_is_enchantment(self) -> None:
        card = GloriousAnthem(name="Glorious Anthem", owner=None)
        assert isinstance(card, Enchantment)
        assert CardType.ENCHANTMENT in card.card_types
    def test_not_aura(self) -> None:
        card = GloriousAnthem(name="Glorious Anthem", owner=None)
        assert not card.is_aura

@pytest.mark.ability
class TestGloriousAnthemAbility:
    def test_buffs_own_creature_power(self) -> None:
        """Glorious Anthem gives +1/+1 to your creatures."""
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        anthem = GloriousAnthem(name="Glorious Anthem", owner=game.players[0])
        anthem.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, anthem])
        anthem.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 3
        assert c.base_toughness == 3
    def test_buffs_multiple_creatures(self) -> None:
        """All creatures controlled by the anthem's controller get the buff."""
        game = create_game()
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[0])
        anthem = GloriousAnthem(name="Glorious Anthem", owner=game.players[0])
        anthem.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c1, c2, anthem])
        anthem.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c1.base_power == 3
        assert c2.base_power == 4

@pytest.mark.edge
class TestGloriousAnthemEdge:
    def test_does_not_buff_opponent_creatures(self) -> None:
        """Glorious Anthem only affects your creatures, not opponent's."""
        game = create_game()
        own_c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        opp_c = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[1])
        anthem = GloriousAnthem(name="Glorious Anthem", owner=game.players[0])
        anthem.controller = game.players[0]
        set_board_state(game, 0, battlefield=[own_c, anthem])
        set_board_state(game, 1, battlefield=[opp_c])
        anthem.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert opp_c.base_power == 3  # unchanged
        assert opp_c.base_toughness == 3

    def test_buff_stops_when_anthem_leaves_battlefield(self) -> None:
        """Once Glorious Anthem leaves the battlefield, the +1/+1 should stop applying."""
        from engine.game import destroy
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        anthem = GloriousAnthem(name="Glorious Anthem", owner=game.players[0])
        anthem.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, anthem])
        anthem.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 3  # buffed
        # Remove anthem from battlefield
        destroy(game, anthem)
        # Re-apply effects — creature should revert
        game.effect_manager.apply_all(game)
        assert c.base_power == 2, "Buff should stop after anthem leaves battlefield"
