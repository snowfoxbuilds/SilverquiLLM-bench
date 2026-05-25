"""Audited tests for FDN 4 — Cat Collector."""
from __future__ import annotations
from card_impl import CatCollector
from engine.card import Artifact, Creature
from engine.types import CardType, Keyword, ManaCost
from test_utils import create_game
from engine.events import GainsLifeTriggeredEvent

class TestCatCollectorBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = CatCollector(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CatCollector(owner=None)
        assert card.name == 'Cat Collector'

    def test_mana_cost(self) -> None:
        card = CatCollector(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{W}')

    def test_power_toughness(self) -> None:
        card = CatCollector(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = CatCollector(owner=None)
        assert 'Human' in card.subtypes
        assert 'Citizen' in card.subtypes

class TestCatCollectorETB:
    """ETB creates a Food token."""

    def test_etb_creates_food_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cc = CatCollector(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(cc)
        cc.on_resolve(game)
        foods = [c for c in bf.get_all() if 'Food' in getattr(c, 'subtypes', set())]
        assert len(foods) == 1

    def test_food_token_is_artifact(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cc = CatCollector(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(cc)
        cc.on_resolve(game)
        foods = [c for c in bf.get_all() if 'Food' in getattr(c, 'subtypes', set())]
        assert len(foods) == 1
        assert CardType.ARTIFACT in foods[0].card_types

class TestCatCollectorLifeGainTrigger:
    """First life gain per turn creates Cat token."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup_trigger(self):
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        cc = CatCollector(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(cc)
        cc.register_triggers(game)
        return (game, cc, p1, bf)

    def test_first_life_gain_creates_cat(self) -> None:
        game, cc, p1, bf = self._setup_trigger()
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=3))
        self._resolve_stack(game)
        cats = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Cat' and getattr(c, 'is_token', False)]
        assert len(cats) == 1

    def test_second_life_gain_same_turn_no_cat(self) -> None:
        game, cc, p1, bf = self._setup_trigger()
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=3))
        self._resolve_stack(game)
        count_after_first = len([c for c in bf.get_all() if getattr(c, 'name', '') == 'Cat' and getattr(c, 'is_token', False)])
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=2))
        self._resolve_stack(game)
        count_after_second = len([c for c in bf.get_all() if getattr(c, 'name', '') == 'Cat' and getattr(c, 'is_token', False)])
        assert count_after_second == count_after_first, 'No second Cat should be created'

    def test_no_trigger_on_opponent_turn(self) -> None:
        game, cc, p1, bf = self._setup_trigger()
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=3))
        self._resolve_stack(game)
        cats = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Cat' and getattr(c, 'is_token', False)]
        assert len(cats) == 0
