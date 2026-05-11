"""Audited tests for Banishing Light (FDN collector number 138)."""
from __future__ import annotations
import pytest
from card_impl import BanishingLight
from engine.card import Enchantment
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestBanishingLightBasic:
    def test_is_enchantment(self) -> None:
        card = BanishingLight(name="Banishing Light", owner=None)
        assert isinstance(card, Enchantment)
        assert CardType.ENCHANTMENT in card.card_types
    def test_name(self) -> None:
        card = BanishingLight(name="Banishing Light", owner=None)
        assert card.name == "Banishing Light"
