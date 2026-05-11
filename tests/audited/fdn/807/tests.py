"""Audited tests for Altar of the Brood (FDN — synthetic dir 807)."""
from __future__ import annotations
import pytest
from card_impl import AltarOfTheBrood
from engine.card import Artifact
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestAltarOfTheBroodBasic:
    def test_is_artifact(self) -> None:
        card = AltarOfTheBrood(name="Altar of the Brood", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        assert AltarOfTheBrood(name="Altar of the Brood", owner=None).name == "Altar of the Brood"
