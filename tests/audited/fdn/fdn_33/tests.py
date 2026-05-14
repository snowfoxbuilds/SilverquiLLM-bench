"""Audited tests for FDN 33 — Clinquant Skymage."""

from __future__ import annotations

from card_impl import ClinquantSkymage
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestClinquantSkymageBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ClinquantSkymage(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ClinquantSkymage(owner=None)
        assert card.name == "Clinquant Skymage"

    def test_mana_cost(self) -> None:
        card = ClinquantSkymage(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")

    def test_power_toughness(self) -> None:
        card = ClinquantSkymage(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_flying(self) -> None:
        card = ClinquantSkymage(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = ClinquantSkymage(owner=None)
        assert "Bird" in card.subtypes
        assert "Wizard" in card.subtypes


class TestClinquantSkymageDrawTrigger:
    """Whenever you draw a card, put a +1/+1 counter on this creature."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        skymage = ClinquantSkymage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(skymage)
        skymage.register_triggers(game)
        return game, skymage, p1

    def test_gets_counter_on_draw(self) -> None:
        from engine.triggers import EventType
        game, skymage, p1 = self._setup()
        initial = skymage.plus_one_counters
        game.trigger_manager.fire_event(
            game, EventType.DRAWS_CARD, {"player": p1},
        )
        self._resolve_stack(game)
        assert skymage.plus_one_counters == initial + 1

    def test_multiple_draws_multiple_counters(self) -> None:
        from engine.triggers import EventType
        game, skymage, p1 = self._setup()
        initial = skymage.plus_one_counters
        for _ in range(3):
            game.trigger_manager.fire_event(
                game, EventType.DRAWS_CARD, {"player": p1},
            )
            self._resolve_stack(game)
        assert skymage.plus_one_counters == initial + 3

    def test_no_counter_on_opponent_draw(self) -> None:
        from engine.triggers import EventType
        game, skymage, p1 = self._setup()
        p2 = game.players[1]
        initial = skymage.plus_one_counters
        game.trigger_manager.fire_event(
            game, EventType.DRAWS_CARD, {"player": p2},
        )
        self._resolve_stack(game)
        assert skymage.plus_one_counters == initial
