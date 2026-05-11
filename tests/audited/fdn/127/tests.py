"""Audited tests for Banner of Kinship (FDN collector number 127)."""
from __future__ import annotations
import pytest
from card_impl import BannerOfKinship
from engine.card import Artifact
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestBannerOfKinshipBasic:
    def test_is_artifact(self) -> None:
        card = BannerOfKinship(name="Banner of Kinship", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = BannerOfKinship(name="Banner of Kinship", owner=None)
        assert card.name == "Banner of Kinship"
