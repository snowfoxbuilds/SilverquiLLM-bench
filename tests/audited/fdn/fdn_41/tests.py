"""Audited tests for FDN 41 — Homunculus Horde."""
from __future__ import annotations
from card_impl import HomunculusHorde
from engine.card import Creature
from engine.types import ManaCost, Zone
from tests.test_utils import create_game
from engine.events import DrawsCardTriggeredEvent

def _resolve_stack(game) -> None:
    """Resolve all items on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestHomunculusHordeBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = HomunculusHorde(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = HomunculusHorde(owner=None)
        assert card.name == 'Homunculus Horde'

    def test_mana_cost(self) -> None:
        card = HomunculusHorde(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{U}')

    def test_power_toughness(self) -> None:
        card = HomunculusHorde(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_homunculus_subtype(self) -> None:
        card = HomunculusHorde(owner=None)
        assert 'Homunculus' in card.subtypes

class TestHomunculusHordeTrigger:
    """Second card draw each turn creates a copy token."""

    def test_first_draw_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HomunculusHorde(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        _resolve_stack(game)
        bf_creatures = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_creatures) == 0

    def test_second_draw_creates_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HomunculusHorde(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        _resolve_stack(game)
        bf_creatures = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_creatures) == 1

    def test_token_is_2_2_homunculus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HomunculusHorde(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        _resolve_stack(game)
        bf_creatures = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        token = bf_creatures[0]
        assert token.base_power == 2
        assert token.base_toughness == 2

    def test_third_draw_same_turn_no_extra_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HomunculusHorde(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        for _ in range(3):
            game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
            _resolve_stack(game)
        bf_creatures = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_creatures) == 1

    def test_new_turn_resets_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HomunculusHorde(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        _resolve_stack(game)
        game.turn_number = 2
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        _resolve_stack(game)
        bf_creatures = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_creatures) == 2

    def test_opponent_draw_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = HomunculusHorde(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p2))
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p2))
        _resolve_stack(game)
        bf_creatures = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_creatures) == 0
