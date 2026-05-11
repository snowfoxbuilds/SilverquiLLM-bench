"""Audited tests for Diamond Mare (FDN collector number 672)."""
from __future__ import annotations
import pytest
from card_impl import DiamondMare
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestDiamondMareBasic:
    def test_is_artifact_creature(self) -> None:
        card = DiamondMare(name="Diamond Mare", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = DiamondMare(name="Diamond Mare", owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3
