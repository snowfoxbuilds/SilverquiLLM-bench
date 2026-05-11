"""Audited tests for Goldvein Pick (FDN collector number 253)."""
from __future__ import annotations
import pytest
from card_impl import GoldveinPick
from engine.card import Artifact, Creature
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestGoldveinPickBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(GoldveinPick(name="Goldvein Pick", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in GoldveinPick(name="Goldvein Pick", owner=None).subtypes

@pytest.mark.ability
class TestGoldveinPickAbility:
    def test_equip_sets_attached(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = GoldveinPick(name="Goldvein Pick", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c
    def test_power_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = GoldveinPick(name="Goldvein Pick", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert c.base_power >= 3
