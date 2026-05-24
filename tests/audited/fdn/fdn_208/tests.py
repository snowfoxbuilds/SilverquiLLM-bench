"""Audited tests for FDN 208 — Spitfire Lagac."""
from __future__ import annotations
from card_impl import SpitfireLagac
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestSpitfireLagacBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SpitfireLagac(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SpitfireLagac(owner=None)
        assert card.name == 'Spitfire Lagac'

    def test_mana_cost(self) -> None:
        card = SpitfireLagac(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{R}')

    def test_power_toughness(self) -> None:
        card = SpitfireLagac(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = SpitfireLagac(owner=None)
        assert 'Lizard' in card.subtypes

class TestSpitfireLagacTrigger:
    """Landfall — Whenever a land you control enters, deals 1 to each opponent."""

    def test_triggers_on_own_land_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lagac = SpitfireLagac(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lagac)
        lagac.register_triggers(game)
        land = CardImpl(name='Mountain', mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p1).add(land)
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        assert p2.life == p2_life_before - 1

    def test_does_not_trigger_on_opponent_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lagac = SpitfireLagac(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lagac)
        lagac.register_triggers(game)
        land = CardImpl(name='Island', mana_cost=ManaCost(generic=0), owner=p2, controller=p2)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p2).add(land)
        p1_life_before = p1.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        assert p1.life == p1_life_before

    def test_does_not_trigger_on_noncreature_nonland(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lagac = SpitfireLagac(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lagac)
        lagac.register_triggers(game)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=creature))
        _resolve_stack(game)
        assert p2.life == p2_life_before
