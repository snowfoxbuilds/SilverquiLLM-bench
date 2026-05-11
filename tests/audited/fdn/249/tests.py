"""Audited tests for Adventuring Gear (FDN collector number 249)."""
from __future__ import annotations
import pytest
from card_impl import AdventuringGear
from engine.card import Artifact, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestAdventuringGearBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(AdventuringGear(name="Adventuring Gear", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in AdventuringGear(name="Adventuring Gear", owner=None).subtypes
    def test_has_equip_ability(self) -> None:
        eq = AdventuringGear(name="Adventuring Gear", owner=None)
        assert len(eq.get_activated_abilities()) > 0

@pytest.mark.ability
class TestAdventuringGearAbility:
    def test_equip_sets_attached(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = AdventuringGear(name="Adventuring Gear", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c
