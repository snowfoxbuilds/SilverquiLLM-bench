"""Audited tests for Leyline Axe (FDN collector number 129, suffix dir)."""
from __future__ import annotations
import pytest
from card_impl import LeylineAxe
from engine.card import Artifact, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestLeylineAxeBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(LeylineAxe(name="Leyline Axe", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in LeylineAxe(name="Leyline Axe", owner=None).subtypes

@pytest.mark.ability
class TestLeylineAxeAbility:
    def test_equip_sets_attached(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = LeylineAxe(name="Leyline Axe", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c
    def test_power_bonus(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = LeylineAxe(name="Leyline Axe", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert c.base_power >= 3
    def test_grants_double_strike(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = LeylineAxe(name="Leyline Axe", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.DOUBLE_STRIKE in c.keywords
    def test_grants_trample(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = LeylineAxe(name="Leyline Axe", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.TRAMPLE in c.keywords
