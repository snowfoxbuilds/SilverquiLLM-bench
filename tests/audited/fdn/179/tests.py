"""Audited tests for Painful Quandary (FDN collector number 179)."""
from __future__ import annotations
import pytest
from card_impl import PainfulQuandary
from engine.card import Enchantment
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestPainfulQuandaryBasic:
    def test_is_enchantment(self) -> None:
        card = PainfulQuandary(name="Painful Quandary", owner=None)
        assert isinstance(card, Enchantment)
    def test_name(self) -> None:
        card = PainfulQuandary(name="Painful Quandary", owner=None)
        assert card.name == "Painful Quandary"
