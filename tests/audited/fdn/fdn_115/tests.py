"""Audited tests for FDN 115 — Alesha, Who Laughs at Fate."""
from __future__ import annotations
from card_impl import AleshaWhoLaughsAtFate
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import AttacksTriggeredEvent, EndStepTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestAleshaBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = AleshaWhoLaughsAtFate(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AleshaWhoLaughsAtFate(owner=None)
        assert card.name == 'Alesha, Who Laughs at Fate'

    def test_mana_cost(self) -> None:
        card = AleshaWhoLaughsAtFate(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{B}{R}')

    def test_power_toughness(self) -> None:
        card = AleshaWhoLaughsAtFate(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_is_legendary(self) -> None:
        card = AleshaWhoLaughsAtFate(owner=None)
        assert 'Legendary' in getattr(card, 'supertypes', set())

    def test_has_first_strike(self) -> None:
        card = AleshaWhoLaughsAtFate(owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords

    def test_subtypes(self) -> None:
        card = AleshaWhoLaughsAtFate(owner=None)
        assert 'Human' in card.subtypes
        assert 'Warrior' in card.subtypes

class TestAleshaAttackTrigger:
    """Attack trigger: +1/+1 counter."""

    def test_gets_counter_on_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        alesha = AleshaWhoLaughsAtFate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(alesha)
        alesha.register_triggers(game)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=alesha))
        _resolve_stack(game)
        assert getattr(alesha, 'plus_one_counters', 0) >= 1

    def test_no_counter_when_other_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        alesha = AleshaWhoLaughsAtFate(owner=p1, controller=p1)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(alesha)
        game.get_battlefield(p1).add(other)
        alesha.register_triggers(game)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=other))
        _resolve_stack(game)
        assert getattr(alesha, 'plus_one_counters', 0) == 0

class TestAleshaRaidTrigger:
    """Raid end-step trigger: return creature from graveyard."""

    def test_raid_returns_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        alesha = AleshaWhoLaughsAtFate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(alesha)
        target = Creature(name='Goblin', base_power=1, base_toughness=1, mana_cost=ManaCost.parse('{R}'), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        alesha.register_triggers(game)
        game.active_player_index = 0
        game.attacked_this_turn = True
        p1.attacked_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert game.get_battlefield(p1).contains(target)

    def test_raid_does_not_trigger_without_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        alesha = AleshaWhoLaughsAtFate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(alesha)
        target = Creature(name='Goblin', base_power=1, base_toughness=1, mana_cost=ManaCost.parse('{R}'), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        alesha.register_triggers(game)
        game.active_player_index = 0
        game.attacked_this_turn = False
        p1.attacked_this_turn = False
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(target)

    def test_raid_respects_mana_value_limit(self) -> None:
        game = create_game()
        p1 = game.players[0]
        alesha = AleshaWhoLaughsAtFate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(alesha)
        big = Creature(name='Angel', base_power=4, base_toughness=4, mana_cost=ManaCost.parse('{3}{W}{W}'), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(big)
        alesha.register_triggers(game)
        game.active_player_index = 0
        game.attacked_this_turn = True
        p1.attacked_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(big)

    def test_raid_checks_active_player_guard(self) -> None:
        """Raid only triggers on controller's end step."""
        game = create_game()
        p1 = game.players[0]
        alesha = AleshaWhoLaughsAtFate(owner=p1, controller=p1)
        game.get_battlefield(p1).add(alesha)
        target = Creature(name='Goblin', base_power=1, base_toughness=1, mana_cost=ManaCost.parse('{R}'), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        alesha.register_triggers(game)
        game.active_player_index = 1
        game.attacked_this_turn = True
        p1.attacked_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        _resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(target)
