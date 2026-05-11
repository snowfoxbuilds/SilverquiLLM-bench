"""Audited tests for Quick-Draw Katana (FDN collector number 130)."""
from __future__ import annotations
import pytest
from card_impl import QuickDrawKatana
from engine.card import Artifact, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestQuickDrawKatanaBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(QuickDrawKatana(name="Quick-Draw Katana", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in QuickDrawKatana(name="Quick-Draw Katana", owner=None).subtypes
    def test_has_equip_ability(self) -> None:
        eq = QuickDrawKatana(name="Quick-Draw Katana", owner=None)
        assert len(eq.get_activated_abilities()) > 0

@pytest.mark.ability
class TestQuickDrawKatanaAbility:
    def test_equip_sets_attached(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = QuickDrawKatana(name="Quick-Draw Katana", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c
