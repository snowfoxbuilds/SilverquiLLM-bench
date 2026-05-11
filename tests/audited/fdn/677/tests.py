"""Audited tests for Pyromancer\'s Goggles (FDN collector number 677)."""
from __future__ import annotations
import pytest
from card_impl import PyromancersGoggles
from engine.card import Artifact
from engine.types import ManaType, Supertype
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestPyromancersGogglesBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(PyromancersGoggles(name="Pyromancer\'s Goggles", owner=None), Artifact)
    def test_is_legendary(self) -> None:
        card = PyromancersGoggles(name="Pyromancer\'s Goggles", owner=None)
        assert Supertype.LEGENDARY in card.supertypes

@pytest.mark.ability
class TestPyromancersGogglesAbility:
    def test_taps_for_red(self) -> None:
        game = create_game()
        card = PyromancersGoggles(name="Pyromancer\'s Goggles", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.RED) >= 1
