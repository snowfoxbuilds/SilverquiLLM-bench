"""Audited tests for FDN 245 — Ruby, Daring Tracker."""
from __future__ import annotations
from card_impl import RubyDaringTracker
from engine.card import Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game
from engine.events import AttacksTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestRubyBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = RubyDaringTracker(owner=None)
        assert card.name == 'Ruby, Daring Tracker'

    def test_mana_cost(self) -> None:
        card = RubyDaringTracker(owner=None)
        assert card.mana_cost == ManaCost.parse('{R}{G}')

    def test_power_toughness(self) -> None:
        card = RubyDaringTracker(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 2

    def test_has_haste(self) -> None:
        card = RubyDaringTracker(owner=None)
        assert Keyword.HASTE & card.keywords

    def test_is_legendary(self) -> None:
        card = RubyDaringTracker(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = RubyDaringTracker(owner=None)
        assert 'Human' in card.subtypes
        assert 'Scout' in card.subtypes

class TestRubyAttackTrigger:
    """Gets +2/+2 when attacking if you control power 4+ creature."""

    def test_gets_buff_with_big_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ruby = RubyDaringTracker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ruby)
        big = Creature(name='Big', base_power=4, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(big)
        ruby.register_triggers(game)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=ruby))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ruby.modified_power == 3
        assert ruby.modified_toughness == 4

    def test_no_buff_without_big_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ruby = RubyDaringTracker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ruby)
        small = Creature(name='Small', base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(small)
        ruby.register_triggers(game)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=ruby))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ruby.base_power == 1
        assert ruby.base_toughness == 2

class TestRubyManaAbilities:
    """Tap: Add {R} or {G}."""

    def test_has_mana_abilities(self) -> None:
        ruby = RubyDaringTracker(owner=None)
        abilities = ruby.get_mana_abilities()
        assert len(abilities) == 2

    def test_produces_red(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ruby = RubyDaringTracker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ruby)
        abilities = ruby.get_mana_abilities()
        red_ability = abilities[0]
        red_ability.mana_produced(game)
        assert p1.mana_pool.get(ManaType.RED) >= 1
