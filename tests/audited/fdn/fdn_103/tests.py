"""Audited tests for FDN 103 — Elfsworn Giant."""
from __future__ import annotations
from card_impl import ElfswornGiant
from engine.card import Creature, Land
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestElfswornGiantBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ElfswornGiant(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ElfswornGiant(owner=None)
        assert card.name == 'Elfsworn Giant'

    def test_mana_cost(self) -> None:
        card = ElfswornGiant(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{G}{G}')

    def test_power_toughness(self) -> None:
        card = ElfswornGiant(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 3

    def test_has_reach(self) -> None:
        card = ElfswornGiant(owner=None)
        assert Keyword.REACH in card.keywords

    def test_subtypes(self) -> None:
        card = ElfswornGiant(owner=None)
        assert 'Giant' in card.subtypes

class TestElfswornGiantLandfall:
    """Landfall: create 1/1 Elf Warrior token when a land you control enters."""

    def test_creates_token_on_land_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giant = ElfswornGiant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(giant)
        giant.register_triggers(game)
        land = Land(name='Forest', owner=p1, controller=p1)
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Elf Warrior']
        assert len(tokens) == 1
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1

    def test_no_token_on_opponent_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        giant = ElfswornGiant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(giant)
        giant.register_triggers(game)
        land = Land(name='Forest', owner=p2, controller=p2)
        game.get_battlefield(p2).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Elf Warrior']
        assert len(tokens) == 0

    def test_no_token_on_creature_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giant = ElfswornGiant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(giant)
        giant.register_triggers(game)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=creature))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Elf Warrior']
        assert len(tokens) == 0
