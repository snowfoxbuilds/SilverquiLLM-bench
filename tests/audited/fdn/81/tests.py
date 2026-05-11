"""Audited tests for Chandra, Flameshaper (FDN collector number 81)."""
from __future__ import annotations
import pytest
from card_impl import ChandraFlameshaper
from engine.card import Planeswalker
from engine.types import CardType, Supertype, ManaType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestChandraFlameshaperBasic:
    def test_is_planeswalker(self) -> None:
        card = ChandraFlameshaper(name="Chandra, Flameshaper", owner=None)
        assert isinstance(card, Planeswalker)
    def test_starting_loyalty(self) -> None:
        card = ChandraFlameshaper(name="Chandra, Flameshaper", owner=None)
        assert card.loyalty == 6

@pytest.mark.ability
class TestChandraFlameshaperAbilities:
    def test_has_three_loyalty_abilities(self) -> None:
        card = ChandraFlameshaper(name="Chandra, Flameshaper", owner=None)
        assert len(card.get_loyalty_abilities()) == 3
    def test_plus2_adds_red_mana(self) -> None:
        game = create_game()
        pw = ChandraFlameshaper(name="Chandra, Flameshaper", owner=game.players[0])
        pw.controller = game.players[0]
        set_board_state(game, 0, battlefield=[pw])
        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)  # +2: Add RRR
        assert game.players[0].mana_pool.get(ManaType.RED) >= 3
    def test_plus2_cost(self) -> None:
        card = ChandraFlameshaper(name="Chandra, Flameshaper", owner=None)
        assert card.get_loyalty_abilities()[0].loyalty_cost == +2
    def test_minus4_cost(self) -> None:
        card = ChandraFlameshaper(name="Chandra, Flameshaper", owner=None)
        assert card.get_loyalty_abilities()[2].loyalty_cost == -4
