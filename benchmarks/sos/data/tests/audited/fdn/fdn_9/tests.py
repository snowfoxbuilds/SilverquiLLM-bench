"""Audited tests for FDN 9 — Dazzling Angel."""
from __future__ import annotations
from card_impl import DazzlingAngel
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent

class TestDazzlingAngelBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = DazzlingAngel(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = DazzlingAngel(owner=None)
        assert card.name == 'Dazzling Angel'

    def test_mana_cost(self) -> None:
        card = DazzlingAngel(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{W}')

    def test_power_toughness(self) -> None:
        card = DazzlingAngel(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = DazzlingAngel(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_angel_subtype(self) -> None:
        card = DazzlingAngel(owner=None)
        assert 'Angel' in card.subtypes

class TestDazzlingAngelETBTrigger:
    """Whenever another creature you control enters, gain 1 life."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup_trigger(self):
        game = create_game()
        p1 = game.players[0]
        angel = DazzlingAngel(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(angel)
        angel.register_triggers(game)
        return (game, angel, p1, bf)

    def test_another_creature_entering_gains_life(self) -> None:
        game, angel, p1, bf = self._setup_trigger()
        initial_life = p1.life
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        bf.add(other)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=other, controller=p1))
        self._resolve_stack(game)
        assert p1.life == initial_life + 1

    def test_self_entering_does_not_trigger(self) -> None:
        game, angel, p1, bf = self._setup_trigger()
        initial_life = p1.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=angel, controller=p1))
        self._resolve_stack(game)
        assert p1.life == initial_life

    def test_opponent_creature_does_not_trigger(self) -> None:
        game, angel, p1, bf = self._setup_trigger()
        p2 = game.players[1]
        initial_life = p1.life
        opp_creature = Creature(name='Goblin', base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_creature)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=opp_creature, controller=p2))
        self._resolve_stack(game)
        assert p1.life == initial_life
