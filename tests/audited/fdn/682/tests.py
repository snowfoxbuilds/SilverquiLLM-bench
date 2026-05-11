"""Audited tests for Three Tree Mascot (FDN collector number 682)."""
from __future__ import annotations
import pytest
from card_impl import ThreeTreeMascot
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestThreeTreeMascotBasic:
    def test_is_artifact_creature(self) -> None:
        card = ThreeTreeMascot(name="Three Tree Mascot", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = ThreeTreeMascot(name="Three Tree Mascot", owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1
    def test_is_changeling(self) -> None:
        card = ThreeTreeMascot(name="Three Tree Mascot", owner=None)
        assert getattr(card, "is_changeling", False)
