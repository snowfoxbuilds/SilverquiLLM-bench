"""Audited tests for FDN 111 — Quilled Greatwurm."""

from __future__ import annotations

from card_impl import QuilledGreatwurm
from engine.card import Creature
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestQuilledGreatwurmBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = QuilledGreatwurm(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = QuilledGreatwurm(owner=None)
        assert card.name == "Quilled Greatwurm"

    def test_mana_cost(self) -> None:
        card = QuilledGreatwurm(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{G}{G}")

    def test_power_toughness(self) -> None:
        card = QuilledGreatwurm(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_trample(self) -> None:
        card = QuilledGreatwurm(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_subtypes(self) -> None:
        card = QuilledGreatwurm(owner=None)
        assert "Wurm" in card.subtypes


class TestQuilledGreatwurmCombatDamage:
    """When a creature you control deals combat damage during your turn,
    put that many +1/+1 counters on it."""

    def test_puts_counters_equal_to_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wurm = QuilledGreatwurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)
        game.active_player_index = 0  # p1's turn
        wurm.register_triggers(game)
        attacker = Creature(name="Bear", base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(attacker)
        game.trigger_manager.fire_event(
            game, EventType.DEALS_DAMAGE,
            {"source": attacker, "target": p2, "amount": 3, "is_combat": True}
        )
        _resolve_stack(game)
        assert attacker.plus_one_counters == 3
        assert attacker._original_plus_one_counters == 3

    def test_noncombat_damage_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wurm = QuilledGreatwurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)
        game.active_player_index = 0
        wurm.register_triggers(game)
        attacker = Creature(name="Bear", base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(attacker)
        game.trigger_manager.fire_event(
            game, EventType.DEALS_DAMAGE,
            {"source": attacker, "target": p2, "amount": 3, "is_combat": False}
        )
        _resolve_stack(game)
        assert attacker.plus_one_counters == 0

    def test_not_your_turn_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wurm = QuilledGreatwurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)
        game.active_player_index = 1  # p2's turn
        wurm.register_triggers(game)
        attacker = Creature(name="Bear", base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(attacker)
        game.trigger_manager.fire_event(
            game, EventType.DEALS_DAMAGE,
            {"source": attacker, "target": p2, "amount": 3, "is_combat": True}
        )
        _resolve_stack(game)
        assert attacker.plus_one_counters == 0

    def test_opponent_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wurm = QuilledGreatwurm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wurm)
        game.active_player_index = 0
        wurm.register_triggers(game)
        opp_attacker = Creature(name="Opp", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_attacker)
        game.trigger_manager.fire_event(
            game, EventType.DEALS_DAMAGE,
            {"source": opp_attacker, "target": p1, "amount": 2, "is_combat": True}
        )
        _resolve_stack(game)
        assert opp_attacker.plus_one_counters == 0
