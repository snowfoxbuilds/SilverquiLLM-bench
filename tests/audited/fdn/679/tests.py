"""Audited tests for Sorcerous Spyglass (FDN collector number 679)."""
from __future__ import annotations
import pytest
from card_impl import SorcerousSpyglass
from engine.card import Artifact
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestSorcerousSpyglassBasic:
    def test_is_artifact(self) -> None:
        card = SorcerousSpyglass(name="Sorcerous Spyglass", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = SorcerousSpyglass(name="Sorcerous Spyglass", owner=None)
        assert card.name == "Sorcerous Spyglass"
