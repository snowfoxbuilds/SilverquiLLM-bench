"""Audited tests for Phyrexian Arena (FDN collector number 180)."""
from __future__ import annotations
import pytest
from card_impl import PhyrexianArena
from engine.card import Enchantment
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestPhyrexianArenaBasic:
    def test_is_enchantment(self) -> None:
        card = PhyrexianArena(name="Phyrexian Arena", owner=None)
        assert isinstance(card, Enchantment)
    def test_name(self) -> None:
        card = PhyrexianArena(name="Phyrexian Arena", owner=None)
        assert card.name == "Phyrexian Arena"
