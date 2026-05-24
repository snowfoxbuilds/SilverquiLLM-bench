"""Audited tests for FDN 123 — Niv-Mizzet, Visionary."""
from __future__ import annotations
from card_impl import NivMizzetVisionary
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import DealsDamageTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestNivMizzetBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = NivMizzetVisionary(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = NivMizzetVisionary(owner=None)
        assert card.name == 'Niv-Mizzet, Visionary'

    def test_mana_cost(self) -> None:
        card = NivMizzetVisionary(owner=None)
        assert card.mana_cost == ManaCost.parse('{4}{U}{R}')

    def test_power_toughness(self) -> None:
        card = NivMizzetVisionary(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        card = NivMizzetVisionary(owner=None)
        assert 'Legendary' in getattr(card, 'supertypes', set())

    def test_has_flying(self) -> None:
        card = NivMizzetVisionary(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = NivMizzetVisionary(owner=None)
        assert 'Dragon' in card.subtypes
        assert 'Wizard' in card.subtypes

class TestNivMizzetAbilities:
    """No max hand size and noncombat damage trigger."""

    def test_sets_no_max_hand_size(self) -> None:
        game = create_game()
        p1 = game.players[0]
        niv = NivMizzetVisionary(owner=p1, controller=p1)
        game.get_battlefield(p1).add(niv)
        niv.register_triggers(game)
        assert getattr(p1, 'no_maximum_hand_size', False) is True

    def test_draws_on_noncombat_damage_to_opponent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        niv = NivMizzetVisionary(owner=p1, controller=p1)
        game.get_battlefield(p1).add(niv)
        for i in range(3):
            c = Creature(name=f'Card{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        niv.register_triggers(game)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        dmg_source = Creature(name='Pinger', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=dmg_source, target=p2, amount=2, is_combat=False))
        _resolve_stack(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after > hand_before

    def test_no_draw_on_combat_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        niv = NivMizzetVisionary(owner=p1, controller=p1)
        game.get_battlefield(p1).add(niv)
        for i in range(3):
            c = Creature(name=f'Card{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        niv.register_triggers(game)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=niv, target=p2, amount=5, is_combat=True))
        _resolve_stack(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before

    def test_no_draw_on_damage_to_self(self) -> None:
        game = create_game()
        p1 = game.players[0]
        niv = NivMizzetVisionary(owner=p1, controller=p1)
        game.get_battlefield(p1).add(niv)
        for i in range(3):
            c = Creature(name=f'Card{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        niv.register_triggers(game)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=niv, target=p1, amount=3, is_combat=False))
        _resolve_stack(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before

    def test_unregister_removes_no_max_hand_size(self) -> None:
        game = create_game()
        p1 = game.players[0]
        niv = NivMizzetVisionary(owner=p1, controller=p1)
        game.get_battlefield(p1).add(niv)
        niv.register_triggers(game)
        niv.unregister_triggers(game)
        assert getattr(p1, 'no_maximum_hand_size', True) is False
