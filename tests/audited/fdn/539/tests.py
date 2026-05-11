"""Audited tests for Goblin Oriflamme (FDN collector number 539)."""
from __future__ import annotations
import pytest
from card_impl import GoblinOriflamme
from engine.card import Enchantment, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestGoblinOriflammeBasic:
    def test_is_enchantment(self) -> None:
        card = GoblinOriflamme(name="Goblin Oriflamme", owner=None)
        assert isinstance(card, Enchantment)
        assert CardType.ENCHANTMENT in card.card_types
    def test_not_aura(self) -> None:
        card = GoblinOriflamme(name="Goblin Oriflamme", owner=None)
        assert not card.is_aura

@pytest.mark.ability
class TestGoblinOriflammeAbility:
    def test_buffs_attacking_creature_power(self) -> None:
        """Attacking creatures you control get +1/+0."""
        game = create_game()
        c = Creature(name="Goblin", base_power=1, base_toughness=1, owner=game.players[0])
        c.is_attacking = True
        ench = GoblinOriflamme(name="Goblin Oriflamme", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 2

@pytest.mark.edge
class TestGoblinOriflammeEdge:
    def test_does_not_buff_non_attacking_creature(self) -> None:
        """Non-attacking creatures should not get the buff."""
        game = create_game()
        c = Creature(name="Goblin", base_power=1, base_toughness=1, owner=game.players[0])
        c.is_attacking = False
        ench = GoblinOriflamme(name="Goblin Oriflamme", owner=game.players[0])
        ench.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, ench])
        ench.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 1
