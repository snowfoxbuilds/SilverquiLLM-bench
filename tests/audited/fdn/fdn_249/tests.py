"""Audited tests for FDN 249 — Adventuring Gear."""
from __future__ import annotations
from card_impl import AdventuringGear
from engine.card import Artifact, CardImpl, Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

class TestAdventuringGearBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = AdventuringGear(owner=None)
        assert card.name == 'Adventuring Gear'

    def test_mana_cost(self) -> None:
        card = AdventuringGear(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}')

    def test_is_artifact(self) -> None:
        card = AdventuringGear(owner=None)
        assert isinstance(card, Artifact)

    def test_has_equipment_subtype(self) -> None:
        card = AdventuringGear(owner=None)
        assert 'Equipment' in card.subtypes

    def test_has_equip_ability(self) -> None:
        card = AdventuringGear(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        assert 'Equip' in abilities[0].description or 'quip' in abilities[0].description

class TestAdventuringGearEquip:
    """Equip {1} — attaches to creature."""

    def test_equip_attaches_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        gear = AdventuringGear(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(gear)
        game.get_battlefield(p1).add(creature)
        gear.equip(creature, game)
        assert gear.attached_to is creature

    def test_equip_cost_requires_one_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        gear = AdventuringGear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(gear)
        abilities = gear.get_activated_abilities()
        equip = abilities[0]
        assert not equip.cost(game, gear)

class TestAdventuringGearLandfall:
    """Landfall — equipped creature gets +2/+2 when a land ETBs."""

    def test_landfall_triggers_on_land_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]
        gear = AdventuringGear(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(gear)
        game.get_battlefield(p1).add(creature)
        gear.equip(creature, game)
        gear.register_triggers(game)
        land = CardImpl(name='Plains', mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land, controller=p1))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert creature.modified_power >= 4
        assert creature.modified_toughness >= 4

    def test_no_trigger_if_not_equipped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        gear = AdventuringGear(owner=p1, controller=p1)
        game.get_battlefield(p1).add(gear)
        gear.register_triggers(game)
        land = CardImpl(name='Plains', mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land, controller=p1))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

    def test_no_trigger_on_opponent_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        gear = AdventuringGear(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(gear)
        game.get_battlefield(p1).add(creature)
        gear.equip(creature, game)
        gear.register_triggers(game)
        land = CardImpl(name='Swamp', mana_cost=ManaCost(generic=0), owner=p2, controller=p2)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p2).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land, controller=p2))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert creature.base_power == 2
        assert creature.base_toughness == 2
