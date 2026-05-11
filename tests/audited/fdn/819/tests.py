"""Audited tests for Chandra, Torch of Defiance (FDN — synthetic dir 819)."""
from __future__ import annotations
import pytest
from card_impl import ChandraTorchOfDefiance
from engine.card import Planeswalker, Creature
from engine.types import CardType, Supertype, ManaType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestChandraTorchBasic:
    def test_is_planeswalker(self) -> None:
        card = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=None)
        assert isinstance(card, Planeswalker)
    def test_starting_loyalty_is_4(self) -> None:
        card = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=None)
        assert card.loyalty == 4
    def test_is_legendary(self) -> None:
        card = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=None)
        assert Supertype.LEGENDARY in card.supertypes

@pytest.mark.ability
class TestChandraTorchAbilities:
    def test_has_four_loyalty_abilities(self) -> None:
        card = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=None)
        assert len(card.get_loyalty_abilities()) == 4
    def test_plus1_mana_adds_two_red(self) -> None:
        """Chandra's +1 mana ability adds exactly {R}{R}."""
        game = create_game()
        pw = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=game.players[0])
        pw.controller = game.players[0]
        set_board_state(game, 0, battlefield=[pw])
        abilities = pw.get_loyalty_abilities()
        mana_ability = abilities[1]  # +1: Add {R}{R}
        mana_ability.effect(game)
        assert game.players[0].mana_pool.get(ManaType.RED) == 2
    def test_minus3_cost(self) -> None:
        pw = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=None)
        assert pw.get_loyalty_abilities()[2].loyalty_cost == -3
    def test_minus7_cost(self) -> None:
        pw = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=None)
        assert pw.get_loyalty_abilities()[3].loyalty_cost == -7
    def test_plus1_exile_deals_damage_to_opponent(self) -> None:
        """Chandra's +1 exile ability deals 2 damage to opponents."""
        game = create_game()
        pw = ChandraTorchOfDefiance(name="Chandra, Torch of Defiance", owner=game.players[0])
        pw.controller = game.players[0]
        set_board_state(game, 0, battlefield=[pw])
        initial_life = game.players[1].life
        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)  # +1: deals 2 to opponents
        assert game.players[1].life == initial_life - 2
