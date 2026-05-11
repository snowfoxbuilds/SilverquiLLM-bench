"""Audited tests for Adaptive Automaton (FDN collector number 723)."""
from __future__ import annotations
import pytest
from card_impl import AdaptiveAutomaton
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestAdaptiveAutomatonBasic:
    def test_is_artifact_creature(self) -> None:
        card = AdaptiveAutomaton(name="Adaptive Automaton", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_power_toughness(self) -> None:
        card = AdaptiveAutomaton(name="Adaptive Automaton", owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2
    def test_has_construct_subtype(self) -> None:
        card = AdaptiveAutomaton(name="Adaptive Automaton", owner=None)
        assert "Construct" in card.subtypes
