"""Audited tests for FDN 83 — Crackling Cyclops."""
from __future__ import annotations
from card_impl import CracklingCyclops
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game
from engine.events import SpellCastTriggeredEvent

class TestCracklingCyclopsBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = CracklingCyclops(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CracklingCyclops(owner=None)
        assert card.name == 'Crackling Cyclops'

    def test_mana_cost(self) -> None:
        card = CracklingCyclops(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{R}')

    def test_power_toughness(self) -> None:
        card = CracklingCyclops(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = CracklingCyclops(owner=None)
        assert 'Cyclops' in card.subtypes
        assert 'Wizard' in card.subtypes

class TestCracklingCyclopsSpellTrigger:
    """Gets +3/+0 when controller casts a noncreature spell."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

    def test_gets_plus3_on_noncreature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CracklingCyclops(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        spell = Instant(name='Bolt', owner=p1, controller=p1)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=spell, player=p1))
        self._resolve_stack(game)
        assert card.base_power == power_before + 3

    def test_no_trigger_on_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CracklingCyclops(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=creature, player=p1))
        self._resolve_stack(game)
        assert card.base_power == power_before

    def test_no_trigger_on_opponent_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = CracklingCyclops(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        spell = Instant(name='Bolt', owner=p2, controller=p2)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=spell, player=p2))
        self._resolve_stack(game)
        assert card.base_power == power_before

    def test_stacks_multiple_noncreature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CracklingCyclops(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        spell1 = Instant(name='Bolt1', owner=p1, controller=p1)
        spell2 = Sorcery(name='Bolt2', owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=spell1, player=p1))
        self._resolve_stack(game)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=spell2, player=p1))
        self._resolve_stack(game)
        assert card.base_power == 6
