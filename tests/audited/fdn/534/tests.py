"""Audited tests for Carnelian Orb of Dragonkind (FDN collector number 534)."""
from __future__ import annotations
import pytest
from card_impl import CarnelianOrbOfDragonkind
from engine.card import Artifact
from engine.types import ManaType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestCarnelianOrbBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(CarnelianOrbOfDragonkind(name="Carnelian Orb of Dragonkind", owner=None), Artifact)

@pytest.mark.ability
class TestCarnelianOrbAbility:
    def test_taps_for_red(self) -> None:
        game = create_game()
        card = CarnelianOrbOfDragonkind(name="Carnelian Orb of Dragonkind", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.RED) >= 1
