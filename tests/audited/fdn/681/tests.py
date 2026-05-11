"""Audited tests for Steel Hellkite (FDN collector number 681)."""
from __future__ import annotations
import pytest
from card_impl import SteelHellkite
from engine.types import CardType, Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestSteelHellkiteBasic:
    def test_is_artifact_creature(self) -> None:
        card = SteelHellkite(name="Steel Hellkite", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = SteelHellkite(name="Steel Hellkite", owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5
    def test_has_flying(self) -> None:
        card = SteelHellkite(name="Steel Hellkite", owner=None)
        assert Keyword.FLYING in card.keywords
