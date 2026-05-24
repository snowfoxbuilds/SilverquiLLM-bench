"""Audited tests for FDN 3 — Armasaur Guide."""
from __future__ import annotations
from card_impl import ArmasaurGuide
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import AttacksTriggeredEvent

class TestArmasaurGuideBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ArmasaurGuide(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ArmasaurGuide(owner=None)
        assert card.name == 'Armasaur Guide'

    def test_mana_cost(self) -> None:
        card = ArmasaurGuide(owner=None)
        assert card.mana_cost == ManaCost.parse('{4}{W}')

    def test_power_toughness(self) -> None:
        card = ArmasaurGuide(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_vigilance(self) -> None:
        card = ArmasaurGuide(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_dinosaur_subtype(self) -> None:
        card = ArmasaurGuide(owner=None)
        assert 'Dinosaur' in card.subtypes

class TestArmasaurGuideAttackTrigger:
    """Attack with 3+ creatures → +1/+1 counter on target."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup_attack(self, num_attackers=3):
        game = create_game()
        p1 = game.players[0]
        guide = ArmasaurGuide(owner=p1, controller=p1)
        creatures = [guide]
        bf = game.get_battlefield(p1)
        bf.add(guide)
        for i in range(num_attackers - 1):
            c = Creature(name=f'Soldier{i}', base_power=1, base_toughness=1, owner=p1, controller=p1)
            bf.add(c)
            creatures.append(c)
        guide.register_triggers(game)
        for c in creatures:
            c.is_attacking = True
        return (game, guide, creatures, p1)

    def test_trigger_fires_with_3_attackers(self) -> None:
        game, guide, creatures, p1 = self._setup_attack(3)
        p1._script.appendleft(guide)
        initial_counters = guide.plus_one_counters
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=guide))
        self._resolve_stack(game)
        assert guide.plus_one_counters == initial_counters + 1

    def test_trigger_does_not_fire_with_2_attackers(self) -> None:
        game, guide, creatures, p1 = self._setup_attack(2)
        initial_counters = guide.plus_one_counters
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=guide))
        self._resolve_stack(game)
        assert guide.plus_one_counters == initial_counters
