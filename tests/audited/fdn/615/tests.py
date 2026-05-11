"""Audited tests for Vampiric Rites (FDN collector number 615)."""
from __future__ import annotations
import pytest
from card_impl import VampiricRites
from engine.card import Enchantment
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestVampiricRitesBasic:
    def test_is_enchantment(self) -> None:
        card = VampiricRites(name="Vampiric Rites", owner=None)
        assert isinstance(card, Enchantment)
    def test_name(self) -> None:
        card = VampiricRites(name="Vampiric Rites", owner=None)
        assert card.name == "Vampiric Rites"
