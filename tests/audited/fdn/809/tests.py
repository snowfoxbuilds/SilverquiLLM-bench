"""Audited tests for Relic of Progenitus (FDN — synthetic dir 809)."""
from __future__ import annotations
import pytest
from card_impl import RelicOfProgenitus
from engine.card import Artifact
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestRelicOfProgenitusBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(RelicOfProgenitus(name="Relic of Progenitus", owner=None), Artifact)
    def test_name(self) -> None:
        assert RelicOfProgenitus(name="Relic of Progenitus", owner=None).name == "Relic of Progenitus"
