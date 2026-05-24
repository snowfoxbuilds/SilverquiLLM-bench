"""Audited tests for FDN 100 — Beast-Kin Ranger."""
from __future__ import annotations
from card_impl import BeastKinRanger
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestBeastKinRangerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = BeastKinRanger(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BeastKinRanger(owner=None)
        assert card.name == 'Beast-Kin Ranger'

    def test_mana_cost(self) -> None:
        card = BeastKinRanger(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{G}')

    def test_power_toughness(self) -> None:
        card = BeastKinRanger(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_trample(self) -> None:
        card = BeastKinRanger(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_subtypes(self) -> None:
        card = BeastKinRanger(owner=None)
        assert 'Elf' in card.subtypes
        assert 'Ranger' in card.subtypes

class TestBeastKinRangerTrigger:
    """Whenever another creature you control enters, +1/+0 until EOT."""

    def test_another_creature_entering_gives_plus_1_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ranger = BeastKinRanger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ranger)
        ranger.register_triggers(game)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=other))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ranger.modified_power == 4

    def test_self_entering_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ranger = BeastKinRanger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ranger)
        ranger.register_triggers(game)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=ranger))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ranger.base_power == 3

    def test_opponent_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ranger = BeastKinRanger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ranger)
        ranger.register_triggers(game)
        opp_creature = Creature(name='Opp Bear', base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_creature)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=opp_creature))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ranger.base_power == 3

    def test_multiple_creatures_entering_stacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ranger = BeastKinRanger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ranger)
        ranger.register_triggers(game)
        for i in range(3):
            c = Creature(name=f'Token{i}', base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)
            game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=c))
            _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ranger.modified_power == 6
