"""Audited tests for Fishing Pole (FDN collector number 128)."""
from __future__ import annotations
import pytest
from card_impl import FishingPole
from engine.card import Artifact
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestFishingPoleBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(FishingPole(name="Fishing Pole", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in FishingPole(name="Fishing Pole", owner=None).subtypes
    def test_name(self) -> None:
        assert FishingPole(name="Fishing Pole", owner=None).name == "Fishing Pole"
