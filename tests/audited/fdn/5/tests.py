"""Audited tests for Celestial Armor (FDN collector number 5)."""
from __future__ import annotations
import pytest
from card_impl import CelestialArmor
from engine.card import Artifact, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestCelestialArmorBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(CelestialArmor(name="Celestial Armor", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in CelestialArmor(name="Celestial Armor", owner=None).subtypes
    def test_name(self) -> None:
        assert CelestialArmor(name="Celestial Armor", owner=None).name == "Celestial Armor"
