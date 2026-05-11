"""Audited tests for Mask of Memory (FDN — synthetic dir 806)."""
from __future__ import annotations
import pytest
from card_impl import MaskOfMemory
from engine.card import Artifact
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestMaskOfMemoryBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(MaskOfMemory(name="Mask of Memory", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in MaskOfMemory(name="Mask of Memory", owner=None).subtypes
    def test_name(self) -> None:
        assert MaskOfMemory(name="Mask of Memory", owner=None).name == "Mask of Memory"
