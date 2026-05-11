"""Audited tests for Scrawling Crawler (FDN collector number 132)."""
from __future__ import annotations
import pytest
from card_impl import ScrawlingCrawler
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestScrawlingCrawlerBasic:
    def test_is_artifact_creature(self) -> None:
        card = ScrawlingCrawler(name="Scrawling Crawler", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_name(self) -> None:
        card = ScrawlingCrawler(name="Scrawling Crawler", owner=None)
        assert card.name == "Scrawling Crawler"
