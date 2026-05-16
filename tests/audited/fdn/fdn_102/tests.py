"""Audited tests for FDN 102 — Eager Trufflesnout."""
from __future__ import annotations
from card_impl import EagerTrufflesnout
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game
from engine.events import DealsDamageTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestEagerTrufflesnoutBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = EagerTrufflesnout(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EagerTrufflesnout(owner=None)
        assert card.name == 'Eager Trufflesnout'

    def test_mana_cost(self) -> None:
        card = EagerTrufflesnout(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{G}')

    def test_power_toughness(self) -> None:
        card = EagerTrufflesnout(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 2

    def test_has_trample(self) -> None:
        card = EagerTrufflesnout(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_subtypes(self) -> None:
        card = EagerTrufflesnout(owner=None)
        assert 'Boar' in card.subtypes

class TestEagerTrufflesnoutCombatDamage:
    """Create a Food token when dealing combat damage to a player."""

    def test_creates_food_on_combat_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        snout = EagerTrufflesnout(owner=p1, controller=p1)
        game.get_battlefield(p1).add(snout)
        snout.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=snout, target=p2, amount=4, is_combat=True))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        foods = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Food']
        assert len(foods) == 1

    def test_food_token_is_artifact_with_food_subtype(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        snout = EagerTrufflesnout(owner=p1, controller=p1)
        game.get_battlefield(p1).add(snout)
        snout.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=snout, target=p2, amount=4, is_combat=True))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        foods = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Food']
        assert len(foods) == 1
        assert 'Food' in foods[0].subtypes

    def test_no_food_on_noncombat_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        snout = EagerTrufflesnout(owner=p1, controller=p1)
        game.get_battlefield(p1).add(snout)
        snout.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=snout, target=p2, amount=4, is_combat=False))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        foods = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Food']
        assert len(foods) == 0

    def test_no_food_on_combat_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        snout = EagerTrufflesnout(owner=p1, controller=p1)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p1).add(snout)
        game.get_battlefield(p2).add(other)
        snout.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=snout, target=other, amount=4, is_combat=True))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        foods = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Food']
        assert len(foods) == 0
