"""Audited tests for Pirate's Cutlass (FDN collector number 563)."""
from __future__ import annotations
import pytest
from card_impl import PiratesCutlass
from engine.card import Artifact
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestPiratesCutlassBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(PiratesCutlass(name="Pirate's Cutlass", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in PiratesCutlass(name="Pirate's Cutlass", owner=None).subtypes
    def test_name(self) -> None:
        assert PiratesCutlass(name="Pirate's Cutlass", owner=None).name == "Pirate's Cutlass"
