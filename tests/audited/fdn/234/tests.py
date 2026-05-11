"""Audited tests for Vivien Reid (FDN collector number 234)."""
from __future__ import annotations
import pytest
from card_impl import VivienReid
from engine.card import Planeswalker
from engine.types import CardType, Supertype
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestVivienReidBasic:
    def test_is_planeswalker(self) -> None:
        card = VivienReid(name="Vivien Reid", owner=None)
        assert isinstance(card, Planeswalker)
    def test_starting_loyalty(self) -> None:
        card = VivienReid(name="Vivien Reid", owner=None)
        assert card.loyalty == 5
    def test_is_legendary(self) -> None:
        card = VivienReid(name="Vivien Reid", owner=None)
        assert Supertype.LEGENDARY in card.supertypes

@pytest.mark.ability
class TestVivienReidAbilities:
    def test_has_three_loyalty_abilities(self) -> None:
        card = VivienReid(name="Vivien Reid", owner=None)
        assert len(card.get_loyalty_abilities()) == 3
    def test_plus1_cost(self) -> None:
        card = VivienReid(name="Vivien Reid", owner=None)
        assert card.get_loyalty_abilities()[0].loyalty_cost == +1
    def test_minus3_cost(self) -> None:
        card = VivienReid(name="Vivien Reid", owner=None)
        assert card.get_loyalty_abilities()[1].loyalty_cost == -3
    def test_minus8_cost(self) -> None:
        card = VivienReid(name="Vivien Reid", owner=None)
        assert card.get_loyalty_abilities()[2].loyalty_cost == -8
