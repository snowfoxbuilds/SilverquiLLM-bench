"""Audited tests for FDN 238 — Consuming Aberration."""
from __future__ import annotations
from card_impl import ConsumingAberration
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import SpellCastTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestConsumingAberrationBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = ConsumingAberration(owner=None)
        assert card.name == 'Consuming Aberration'

    def test_mana_cost(self) -> None:
        card = ConsumingAberration(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{U}{B}')

    def test_is_creature(self) -> None:
        card = ConsumingAberration(owner=None)
        assert isinstance(card, Creature)

    def test_subtypes(self) -> None:
        card = ConsumingAberration(owner=None)
        assert 'Horror' in card.subtypes

class TestConsumingAberrationCDA:
    """P/T = number of cards in opponents' graveyards."""

    def test_pt_equals_opponent_graveyard_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        aberration = ConsumingAberration(owner=p1, controller=p1)
        game.get_battlefield(p1).add(aberration)
        for i in range(3):
            card = CardImpl(name=f'Junk{i}', owner=p2)
            p2.zones[Zone.GRAVEYARD].add(card)
        aberration.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert aberration.modified_power == 3
        assert aberration.modified_toughness == 3

class TestConsumingAberrationMillTrigger:
    """Whenever you cast a spell, mill opponents until a land."""

    def test_mills_until_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        aberration = ConsumingAberration(owner=p1, controller=p1)
        game.get_battlefield(p1).add(aberration)
        nonland1 = CardImpl(name='Spell1', owner=p2)
        nonland1.card_types = {CardType.CREATURE}
        nonland2 = CardImpl(name='Spell2', owner=p2)
        nonland2.card_types = {CardType.CREATURE}
        land = CardImpl(name='Island', owner=p2)
        land.card_types = {CardType.LAND}
        p2.zones[Zone.LIBRARY].add(nonland1)
        p2.zones[Zone.LIBRARY].add(nonland2)
        p2.zones[Zone.LIBRARY].add(land)
        aberration.register_triggers(game)
        spell = CardImpl(name='Something', owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, card=spell))
        _resolve_stack(game)
        gy = p2.zones[Zone.GRAVEYARD]
        gy_cards = list(gy.get_all())
        assert len(gy_cards) >= 1
        land_in_gy = any((CardType.LAND in getattr(c, 'card_types', set()) for c in gy_cards))
        assert land_in_gy
