"""Audited tests for FDN 82 — Courageous Goblin."""

from __future__ import annotations

from card_impl import CourageousGoblin
from engine.card import Creature
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestCourageousGoblinBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = CourageousGoblin(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CourageousGoblin(owner=None)
        assert card.name == "Courageous Goblin"

    def test_mana_cost(self) -> None:
        card = CourageousGoblin(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_power_toughness(self) -> None:
        card = CourageousGoblin(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = CourageousGoblin(owner=None)
        assert "Goblin" in card.subtypes


class TestCourageousGoblinAttackTrigger:
    """Gets +1/+0 and menace when attacking while controlling power 4+ creature."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

    def test_gets_boost_with_power_4_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CourageousGoblin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        big = Creature(name="Big", base_power=4, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(big)
        card.register_triggers(game)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, EventType.ATTACKS, {"creature": card})
        self._resolve_stack(game)
        assert card.base_power == power_before + 1

    def test_gains_menace_with_power_4_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CourageousGoblin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        big = Creature(name="Big", base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(big)
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ATTACKS, {"creature": card})
        self._resolve_stack(game)
        kw = getattr(card, "keywords", Keyword(0)) or Keyword(0)
        assert kw & Keyword.MENACE

    def test_no_boost_without_power_4_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CourageousGoblin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        small = Creature(name="Small", base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(small)
        card.register_triggers(game)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, EventType.ATTACKS, {"creature": card})
        self._resolve_stack(game)
        assert card.base_power == power_before

    def test_does_not_trigger_for_other_creature_attacking(self) -> None:
        """Only triggers when Courageous Goblin itself attacks."""
        game = create_game()
        p1 = game.players[0]
        card = CourageousGoblin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        big = Creature(name="Big", base_power=4, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(big)
        card.register_triggers(game)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, EventType.ATTACKS, {"creature": big})
        self._resolve_stack(game)
        assert card.base_power == power_before
