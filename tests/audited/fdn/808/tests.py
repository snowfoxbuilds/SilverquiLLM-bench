"""Audited tests for Elixir of Immortality (FDN — synthetic dir 808)."""
from __future__ import annotations
import pytest
from card_impl import ElixirOfImmortality
from engine.card import Artifact
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestElixirOfImmortalityBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(ElixirOfImmortality(name="Elixir of Immortality", owner=None), Artifact)
    def test_name(self) -> None:
        assert ElixirOfImmortality(name="Elixir of Immortality", owner=None).name == "Elixir of Immortality"
