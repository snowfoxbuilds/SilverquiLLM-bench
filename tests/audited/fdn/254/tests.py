"""Audited tests for Heraldic Banner (FDN collector number 254)."""
from __future__ import annotations
import pytest
from card_impl import HeraldicBanner
from engine.card import Artifact
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestHeraldicBannerBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(HeraldicBanner(name="Heraldic Banner", owner=None), Artifact)
    def test_has_mana_ability(self) -> None:
        card = HeraldicBanner(name="Heraldic Banner", owner=None)
        assert len(card.get_mana_abilities()) > 0
