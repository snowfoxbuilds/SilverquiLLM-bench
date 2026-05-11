"""Audited tests for Cultivator\'s Caravan (FDN collector number 670)."""
from __future__ import annotations
import pytest
from card_impl import CultivatorsCaravan
from engine.card import Artifact
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestCultivatorsCaravanBasic:
    def test_is_artifact(self) -> None:
        card = CultivatorsCaravan(name="Cultivator\'s Caravan", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_has_mana_ability(self) -> None:
        card = CultivatorsCaravan(name="Cultivator\'s Caravan", owner=None)
        assert len(card.get_mana_abilities()) > 0
