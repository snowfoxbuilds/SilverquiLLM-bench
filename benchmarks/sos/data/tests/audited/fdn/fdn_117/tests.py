"""Audited tests for FDN 117 — Ashroot Animist."""
from __future__ import annotations
from card_impl import AshrootAnimist
from engine.card import Creature
from engine.types import Keyword, ManaCost
from test_utils import create_game
from engine.events import AttacksTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestAshrootAnimistBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = AshrootAnimist(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AshrootAnimist(owner=None)
        assert card.name == 'Ashroot Animist'

    def test_mana_cost(self) -> None:
        card = AshrootAnimist(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{R}{G}')

    def test_power_toughness(self) -> None:
        card = AshrootAnimist(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_trample(self) -> None:
        card = AshrootAnimist(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_subtypes(self) -> None:
        card = AshrootAnimist(owner=None)
        assert 'Lizard' in card.subtypes
        assert 'Druid' in card.subtypes

class TestAshrootAnimistAttackTrigger:
    """Attack trigger: buff another creature."""

    def test_buffs_another_creature_on_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        animist = AshrootAnimist(owner=p1, controller=p1)
        ally = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(animist)
        game.get_battlefield(p1).add(ally)
        animist.register_triggers(game)
        p1._script.appendleft(ally)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=animist))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ally.modified_power >= 6
        assert ally.modified_toughness >= 6

    def test_grants_trample_to_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        animist = AshrootAnimist(owner=p1, controller=p1)
        ally = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(animist)
        game.get_battlefield(p1).add(ally)
        animist.register_triggers(game)
        p1._script.appendleft(ally)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=animist))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert Keyword.TRAMPLE in ally.keywords

    def test_no_trigger_when_other_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        animist = AshrootAnimist(owner=p1, controller=p1)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(animist)
        game.get_battlefield(p1).add(other)
        animist.register_triggers(game)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=other))
        _resolve_stack(game)
        assert other.base_power == 2

    def test_no_crash_when_no_other_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        animist = AshrootAnimist(owner=p1, controller=p1)
        game.get_battlefield(p1).add(animist)
        animist.register_triggers(game)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=animist))
        _resolve_stack(game)
