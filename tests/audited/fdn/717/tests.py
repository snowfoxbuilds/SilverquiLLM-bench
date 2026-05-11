"""Audited tests for Impact Tremors (FDN collector number 717)."""
from __future__ import annotations
import pytest
from card_impl import ImpactTremors
from engine.card import Enchantment
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestImpactTremorsBasic:
    def test_is_enchantment(self) -> None:
        card = ImpactTremors(name="Impact Tremors", owner=None)
        assert isinstance(card, Enchantment)
        assert CardType.ENCHANTMENT in card.card_types
    def test_name(self) -> None:
        card = ImpactTremors(name="Impact Tremors", owner=None)
        assert card.name == "Impact Tremors"
