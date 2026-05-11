"""Audited tests for Basilisk Collar (FDN collector number 669)."""
from __future__ import annotations
import pytest
from card_impl import BasiliskCollar
from engine.card import Artifact, Creature
from engine.types import Keyword
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestBasiliskCollarBasic:
    def test_is_artifact(self) -> None:
        assert isinstance(BasiliskCollar(name="Basilisk Collar", owner=None), Artifact)
    def test_equipment_subtype(self) -> None:
        assert "Equipment" in BasiliskCollar(name="Basilisk Collar", owner=None).subtypes

@pytest.mark.ability
class TestBasiliskCollarAbility:
    def test_grants_deathtouch(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = BasiliskCollar(name="Basilisk Collar", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.DEATHTOUCH in c.keywords
    def test_grants_lifelink(self) -> None:
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = BasiliskCollar(name="Basilisk Collar", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        game.effect_manager.apply_all(game)
        assert Keyword.LIFELINK in c.keywords
    def test_has_equip_ability(self) -> None:
        eq = BasiliskCollar(name="Basilisk Collar", owner=None)
        abilities = eq.get_activated_abilities()
        assert len(abilities) > 0

@pytest.mark.edge
class TestBasiliskCollarEdge:
    def test_reequip_via_activated_ability(self) -> None:
        """Re-equipping via the activated ability pipeline should move to new creature."""
        from engine.types import ManaType
        game = create_game()
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=game.players[0])
        eq = BasiliskCollar(name="Basilisk Collar", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c1, c2, eq], mana={ManaType.COLORLESS: 10})
        eq.equip(c1, game)
        assert eq.attached_to is c1
        # Re-equip via ability
        eq._current_target = c2
        abilities = eq.get_activated_abilities()
        cost_paid = abilities[0].cost(game, eq)
        assert cost_paid
        abilities[0].effect(game)
        assert eq.attached_to is c2

    def test_equipped_creature_dies_equipment_remains(self) -> None:
        """When equipped creature is destroyed, equipment stays on battlefield."""
        from engine.game import destroy
        game = create_game()
        c = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        eq = BasiliskCollar(name="Basilisk Collar", owner=game.players[0])
        eq.controller = game.players[0]
        set_board_state(game, 0, battlefield=[c, eq])
        eq.equip(c, game)
        destroy(game, c)
        bf = game.get_battlefield(game.players[0])
        assert bf.contains(eq), "Equipment should remain on battlefield"
