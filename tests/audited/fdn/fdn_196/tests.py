"""Audited tests for FDN 196 — Firebrand Archer."""
from __future__ import annotations
from card_impl import FirebrandArcher
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost
from tests.test_utils import create_game
from engine.events import SpellCastTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestFirebrandArcherBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = FirebrandArcher(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FirebrandArcher(owner=None)
        assert card.name == 'Firebrand Archer'

    def test_mana_cost(self) -> None:
        card = FirebrandArcher(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{R}')

    def test_power_toughness(self) -> None:
        card = FirebrandArcher(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = FirebrandArcher(owner=None)
        assert 'Human' in card.subtypes
        assert 'Archer' in card.subtypes

class TestFirebrandArcherTrigger:
    """Whenever you cast a noncreature spell, deals 1 damage to each opponent."""

    def test_triggers_on_noncreature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        archer = FirebrandArcher(owner=p1, controller=p1)
        game.get_battlefield(p1).add(archer)
        archer.register_triggers(game)
        noncreature = CardImpl(name='Bolt', mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        noncreature.card_types = {CardType.INSTANT}
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, spell=noncreature))
        _resolve_stack(game)
        assert p2.life == p2_life_before - 1

    def test_does_not_trigger_on_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        archer = FirebrandArcher(owner=p1, controller=p1)
        game.get_battlefield(p1).add(archer)
        archer.register_triggers(game)
        creature_spell = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, spell=creature_spell))
        _resolve_stack(game)
        assert p2.life == p2_life_before

    def test_does_not_trigger_on_opponent_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        archer = FirebrandArcher(owner=p1, controller=p1)
        game.get_battlefield(p1).add(archer)
        archer.register_triggers(game)
        noncreature = CardImpl(name='Bolt', mana_cost=ManaCost(generic=0), owner=p2, controller=p2)
        noncreature.card_types = {CardType.INSTANT}
        p1_life_before = p1.life
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p2, spell=noncreature))
        _resolve_stack(game)
        assert p1.life == p1_life_before
