"""Audited tests for Darksteel Colossus (FDN collector number 671)."""
from __future__ import annotations
import pytest
from card_impl import DarksteelColossus
from engine.types import CardType, Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestDarksteelColossusBasic:
    def test_is_artifact_creature(self) -> None:
        card = DarksteelColossus(name="Darksteel Colossus", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = DarksteelColossus(name="Darksteel Colossus", owner=None)
        assert card.base_power == 11
        assert card.base_toughness == 11
    def test_has_trample(self) -> None:
        card = DarksteelColossus(name="Darksteel Colossus", owner=None)
        assert Keyword.TRAMPLE in card.keywords
    def test_has_indestructible(self) -> None:
        card = DarksteelColossus(name="Darksteel Colossus", owner=None)
        assert Keyword.INDESTRUCTIBLE in card.keywords
