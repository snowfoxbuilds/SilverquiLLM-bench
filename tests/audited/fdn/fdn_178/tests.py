"""Audited tests for FDN 178 — Marauding Blight-Priest."""
from __future__ import annotations
from card_impl import MaraudingBlightPriest
from engine.card import Creature
from engine.types import ManaCost
from tests.test_utils import create_game
from engine.events import GainsLifeTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestMaraudingBlightPriestBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = MaraudingBlightPriest(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = MaraudingBlightPriest(owner=None)
        assert card.name == 'Marauding Blight-Priest'

    def test_mana_cost(self) -> None:
        card = MaraudingBlightPriest(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{B}')

    def test_power_toughness(self) -> None:
        card = MaraudingBlightPriest(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = MaraudingBlightPriest(owner=None)
        assert 'Vampire' in card.subtypes
        assert 'Cleric' in card.subtypes

class TestMaraudingBlightPriestTrigger:
    """Whenever you gain life, each opponent loses 1 life."""

    def test_opponent_loses_life_on_controller_lifegain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        priest = MaraudingBlightPriest(owner=p1, controller=p1)
        game.get_battlefield(p1).add(priest)
        priest.register_triggers(game)
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1))
        _resolve_stack(game)
        assert p2.life == p2_life_before - 1

    def test_does_not_trigger_on_opponent_lifegain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        priest = MaraudingBlightPriest(owner=p1, controller=p1)
        game.get_battlefield(p1).add(priest)
        priest.register_triggers(game)
        p1_life_before = p1.life
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p2))
        _resolve_stack(game)
        assert p1.life == p1_life_before
