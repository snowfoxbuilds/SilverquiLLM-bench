"""Audited tests for Campus Guide (FDN collector number 251)."""
from __future__ import annotations
import pytest
from card_impl import CampusGuide
from engine.card import ArtifactCreature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestCampusGuideBasic:
    def test_is_artifact_creature(self) -> None:
        card = CampusGuide(name="Campus Guide", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = CampusGuide(name="Campus Guide", owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1
