"""Audited tests for Gate Colossus (FDN collector number 675)."""
from __future__ import annotations
import pytest
from card_impl import GateColossus
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestGateColossusBasic:
    def test_is_artifact_creature(self) -> None:
        card = GateColossus(name="Gate Colossus", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = GateColossus(name="Gate Colossus", owner=None)
        assert card.base_power == 8
        assert card.base_toughness == 8
