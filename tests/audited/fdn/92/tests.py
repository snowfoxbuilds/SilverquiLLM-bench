"""Audited tests for Rite of the Dragoncaller (FDN collector number 92)."""
from __future__ import annotations
import pytest
from card_impl import RiteOfTheDragoncaller
from engine.card import Enchantment
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestRiteOfTheDragoncallerBasic:
    def test_is_enchantment(self) -> None:
        card = RiteOfTheDragoncaller(name="Rite of the Dragoncaller", owner=None)
        assert isinstance(card, Enchantment)
    def test_name(self) -> None:
        card = RiteOfTheDragoncaller(name="Rite of the Dragoncaller", owner=None)
        assert card.name == "Rite of the Dragoncaller"
