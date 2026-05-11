"""Audited tests for Crystal Barricade (FDN collector number 7, suffix 'b' for collision)."""
from __future__ import annotations
import pytest
from card_impl import CrystalBarricade
from engine.card import ArtifactCreature
from engine.types import CardType, Keyword
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestCrystalBarricadeBasic:
    def test_is_artifact_creature(self) -> None:
        card = CrystalBarricade(name="Crystal Barricade", owner=None)
        assert isinstance(card, ArtifactCreature)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types

    def test_has_wall_subtype(self) -> None:
        card = CrystalBarricade(name="Crystal Barricade", owner=None)
        assert "Wall" in card.subtypes

    def test_power_toughness(self) -> None:
        card = CrystalBarricade(name="Crystal Barricade", owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 4

    def test_has_defender(self) -> None:
        card = CrystalBarricade(name="Crystal Barricade", owner=None)
        assert Keyword.DEFENDER in card.keywords

    def test_name(self) -> None:
        card = CrystalBarricade(name="Crystal Barricade", owner=None)
        assert card.name == "Crystal Barricade"
