"""Audited tests for FDN 11 — Exemplar of Light."""
from __future__ import annotations
from card_impl import ExemplarOfLight
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game
from engine.events import GainsLifeTriggeredEvent

class TestExemplarOfLightBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ExemplarOfLight(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ExemplarOfLight(owner=None)
        assert card.name == 'Exemplar of Light'

    def test_mana_cost(self) -> None:
        card = ExemplarOfLight(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{W}{W}')

    def test_power_toughness(self) -> None:
        card = ExemplarOfLight(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = ExemplarOfLight(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_angel_subtype(self) -> None:
        card = ExemplarOfLight(owner=None)
        assert 'Angel' in card.subtypes

class TestExemplarLifeGainTrigger:
    """Whenever you gain life, put a +1/+1 counter on this creature."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        exemplar = ExemplarOfLight(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(exemplar)
        exemplar.register_triggers(game)
        return (game, exemplar, p1)

    def test_life_gain_adds_counter(self) -> None:
        game, exemplar, p1 = self._setup()
        initial = exemplar.plus_one_counters
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=3))
        self._resolve_stack(game)
        assert exemplar.plus_one_counters == initial + 1

    def test_multiple_life_gains_add_multiple_counters(self) -> None:
        game, exemplar, p1 = self._setup()
        initial = exemplar.plus_one_counters
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=3))
        self._resolve_stack(game)
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))
        self._resolve_stack(game)
        assert exemplar.plus_one_counters == initial + 2

class TestExemplarDrawTrigger:
    """Whenever +1/+1 counters placed → draw a card, once per turn."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup_with_library(self):
        game = create_game()
        p1 = game.players[0]
        exemplar = ExemplarOfLight(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(exemplar)
        from engine.types import Zone
        for i in range(5):
            c = Creature(name=f'LibCard{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        exemplar.register_triggers(game)
        return (game, exemplar, p1)

    def test_first_counter_triggers_draw(self) -> None:
        game, exemplar, p1 = self._setup_with_library()
        hand_before = len(game.get_hand(p1).get_all())
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))
        self._resolve_stack(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before + 1

    def test_second_counter_same_turn_no_draw(self) -> None:
        game, exemplar, p1 = self._setup_with_library()
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))
        self._resolve_stack(game)
        hand_after_first = len(game.get_hand(p1).get_all())
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))
        self._resolve_stack(game)
        hand_after_second = len(game.get_hand(p1).get_all())
        assert hand_after_second == hand_after_first, 'Draw should only happen once per turn'
