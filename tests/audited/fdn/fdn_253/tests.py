"""Audited tests for FDN 253 — Goldvein Pick."""
from __future__ import annotations
from card_impl import GoldveinPick
from engine.card import Artifact, Creature
from engine.types import CardType, ManaCost, ManaType
from tests.test_utils import create_game
from engine.events import DealsDamageTriggeredEvent

class TestGoldveinPickBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = GoldveinPick(owner=None)
        assert card.name == 'Goldvein Pick'

    def test_mana_cost(self) -> None:
        card = GoldveinPick(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}')

    def test_is_artifact(self) -> None:
        card = GoldveinPick(owner=None)
        assert isinstance(card, Artifact)

    def test_has_equipment_subtype(self) -> None:
        card = GoldveinPick(owner=None)
        assert 'Equipment' in card.subtypes

    def test_has_equip_ability(self) -> None:
        card = GoldveinPick(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

class TestGoldveinPickEquipEffect:
    """Equipped creature gets +1/+1."""

    def test_equip_gives_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pick = GoldveinPick(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(pick)
        game.get_battlefield(p1).add(creature)
        pick.equip(creature, game)
        game.effect_manager.apply_all(game)
        assert creature.base_power >= 3
        assert creature.base_toughness >= 3

class TestGoldveinPickCombatDamage:
    """Whenever equipped creature deals combat damage to a player, create Treasure."""

    def test_creates_treasure_on_combat_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pick = GoldveinPick(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(pick)
        game.get_battlefield(p1).add(creature)
        pick.equip(creature, game)
        pick.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=creature, target=p2, amount=2, is_combat=True))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        treasures = [c for c in bf if getattr(c, 'name', '') == 'Treasure']
        assert len(treasures) >= 1

    def test_no_treasure_on_noncombat_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pick = GoldveinPick(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(pick)
        game.get_battlefield(p1).add(creature)
        pick.equip(creature, game)
        pick.register_triggers(game)
        bf_before = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=creature, target=p2, amount=2, is_combat=False))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after == bf_before

    def test_no_treasure_when_unequipped_creature_hits(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pick = GoldveinPick(owner=p1, controller=p1)
        other_creature = Creature(name='Elf', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(pick)
        game.get_battlefield(p1).add(other_creature)
        pick.register_triggers(game)
        bf_before = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=other_creature, target=p2, amount=1, is_combat=True))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after == bf_before
