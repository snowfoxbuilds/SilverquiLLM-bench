"""Audited tests for Swiftfoot Boots (FDN — synthetic dir 804)."""
from __future__ import annotations
import pytest
from card_impl import SwiftfootBoots
from engine.card import Artifact, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestSwiftfootBootsBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(SwiftfootBoots(name="Swiftfoot Boots", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in SwiftfootBoots(name="Swiftfoot Boots", owner=None).subtypes

@pytest.mark.ability
class TestSwiftfootBootsAbility:
    def test_grants_hexproof(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = SwiftfootBoots(name="Swiftfoot Boots", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in c.keywords
    def test_grants_haste(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = SwiftfootBoots(name="Swiftfoot Boots", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.HASTE in c.keywords
    def test_equip_sets_attached(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = SwiftfootBoots(name="Swiftfoot Boots", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c

@pytest.mark.edge
class TestSwiftfootBootsEdge:
    def test_reequip_changes_attached_creature(self) -> None:
        """Re-equipping moves attachment to the new creature."""
        game = create_game()
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[0])
        eq = SwiftfootBoots(name="Swiftfoot Boots", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c1, c2, eq])
        eq.equip(c1, game)
        assert eq.attached_to is c1
        eq.equip(c2, game)
        assert eq.attached_to is c2
