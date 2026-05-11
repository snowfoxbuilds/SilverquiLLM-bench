"""Audited tests for Bonesplitter (FDN — synthetic dir 803)."""
from __future__ import annotations
import pytest
from card_impl import Bonesplitter
from engine.card import Artifact, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestBonesplitterBasic:
    def test_is_artifact(self) -> None:
        card = Bonesplitter(name="Bonesplitter", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_has_equipment_subtype(self) -> None:
        card = Bonesplitter(name="Bonesplitter", owner=None)
        assert "Equipment" in card.subtypes

@pytest.mark.ability
class TestBonesplitterAbility:
    def test_equip_grants_plus2_power(self) -> None:
        """Equipped creature gets exactly +2/+0."""
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = Bonesplitter(name="Bonesplitter", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert c.base_power == 4  # 2 + 2
    def test_equip_does_not_change_toughness(self) -> None:
        """Bonesplitter gives +2/+0 — toughness should be unchanged."""
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = Bonesplitter(name="Bonesplitter", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert c.base_toughness == 2
    def test_equip_sets_attached(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = Bonesplitter(name="Bonesplitter", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c
    def test_get_activated_abilities_returns_list(self) -> None:
        """Bonesplitter should have get_activated_abilities (may be empty in base impl)."""
        eq = Bonesplitter(name="Bonesplitter", owner=None)
        abilities = eq.get_activated_abilities()
        # Bonesplitter uses direct equip() rather than the activated ability pipeline
        assert isinstance(abilities, list)
    def test_equip_via_direct_method(self) -> None:
        """Equipping via direct equip() method should attach and grant bonus."""
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = Bonesplitter(name="Bonesplitter", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c
        game.effect_manager.apply_all(game)
        assert c.base_power == 4

@pytest.mark.edge
class TestBonesplitterEdge:
    def test_reequip_to_different_creature(self) -> None:
        """Re-equipping should change attached_to to the new creature."""
        game = create_game()
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[0])
        eq = Bonesplitter(name="Bonesplitter", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c1, c2, eq])
        eq.equip(c1, game)
        assert eq.attached_to is c1
        eq.equip(c2, game)
        assert eq.attached_to is c2
    def test_equipped_creature_dies_equipment_stays(self) -> None:
        """When the equipped creature dies, the equipment remains on the battlefield."""
        from engine.game import destroy
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = Bonesplitter(name="Bonesplitter", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        assert eq.attached_to is c
        # Destroy the creature
        destroy(game, c)
        # Equipment should still be on the battlefield
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(eq), "Equipment should remain on battlefield after creature dies"
