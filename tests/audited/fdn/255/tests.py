"""Audited tests for Juggernaut (FDN collector number 255)."""
from __future__ import annotations
import pytest
from card_impl import Juggernaut
from engine.card import ArtifactCreature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestJuggernautBasic:
    def test_is_artifact_creature(self) -> None:
        card = Juggernaut(name="Juggernaut", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = Juggernaut(name="Juggernaut", owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 3
