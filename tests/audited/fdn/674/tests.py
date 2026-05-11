"""Audited tests for Fireshrieker (FDN collector number 674)."""
from __future__ import annotations
import pytest
from card_impl import Fireshrieker
from engine.card import Artifact, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestFireshriekerBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(Fireshrieker(name="Fireshrieker", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in Fireshrieker(name="Fireshrieker", owner=None).subtypes

@pytest.mark.ability
class TestFireshriekerAbility:
    def test_grants_double_strike(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = Fireshrieker(name="Fireshrieker", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.DOUBLE_STRIKE in c.keywords
    def test_has_equip_ability(self) -> None:
        eq = Fireshrieker(name="Fireshrieker", owner=None)
        assert len(eq.get_activated_abilities()) > 0
