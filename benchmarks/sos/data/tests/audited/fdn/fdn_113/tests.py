"""Audited tests for FDN 113 — Sylvan Scavenging."""
from __future__ import annotations
from card_impl import SylvanScavenging
from benchmarks.sos.workspace.engine.card import Creature, Enchantment
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestSylvanScavengingBasics:
    """Basic card properties."""

    def test_is_enchantment(self) -> None:
        card = SylvanScavenging(owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        card = SylvanScavenging(owner=None)
        assert card.name == 'Sylvan Scavenging'

    def test_mana_cost(self) -> None:
        card = SylvanScavenging(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{G}{G}')

class TestSylvanScavengingEndStep:
    """End step: choose counter or token mode."""

    def test_counter_mode_puts_counter_on_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchant = SylvanScavenging(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(enchant)
        game.get_battlefield(p1).add(creature)
        enchant.register_triggers(game)
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(creature)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert creature.plus_one_counters == 1
        assert creature._base_plus_one_counters == 1

    def test_token_mode_creates_raccoon(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchant = SylvanScavenging(owner=p1, controller=p1)
        big_creature = Creature(name='Big', base_power=4, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(enchant)
        game.get_battlefield(p1).add(big_creature)
        enchant.register_triggers(game)
        if isinstance(p1, DeterministicPlayer):
            p1._script.append('token')
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        raccoons = [obj for obj in bf.get_all() if getattr(obj, 'name', '') == 'Raccoon']
        assert len(raccoons) == 1
        assert raccoons[0].base_power == 3
        assert raccoons[0].base_toughness == 3

    def test_no_token_without_power_4_creature(self) -> None:
        """Token mode requires controlling a creature with power 4+."""
        game = create_game()
        p1 = game.players[0]
        enchant = SylvanScavenging(owner=p1, controller=p1)
        small = Creature(name='Small', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(enchant)
        game.get_battlefield(p1).add(small)
        enchant.register_triggers(game)
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(small)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert small.plus_one_counters == 1

    def test_no_creatures_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchant = SylvanScavenging(owner=p1, controller=p1)
        game.get_battlefield(p1).add(enchant)
        enchant.register_triggers(game)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)

    def test_enchantment_not_on_battlefield_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchant = SylvanScavenging(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        enchant.register_triggers(game)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert creature.plus_one_counters == 0
