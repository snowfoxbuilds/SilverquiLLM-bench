"""Audited tests for FDN 125 — Wardens of the Cycle."""

from __future__ import annotations

from card_impl import WardensOfTheCycle
from engine.card import Creature
from engine.triggers import EventType
from engine.types import ManaCost, Zone
from tests.test_utils import create_game


def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestWardensBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.name == "Wardens of the Cycle"

    def test_mana_cost(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}{G}")

    def test_power_toughness(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert "Elf" in card.subtypes
        assert "Warlock" in card.subtypes


class TestWardensMorbid:
    """Morbid end-step trigger: gain life or draw + lose life."""

    def test_gain_life_mode(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wardens)
        wardens.register_triggers(game)
        game.active_player_index = 0
        game.creature_died_this_turn = True
        p1._script.appendleft("gain_life")
        life_before = p1.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p1.life == life_before + 2

    def test_draw_card_mode(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wardens)
        filler = Creature(name="Filler", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(filler)
        wardens.register_triggers(game)
        game.active_player_index = 0
        game.creature_died_this_turn = True
        p1._script.appendleft("draw_card")
        life_before = p1.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p1.life == life_before - 1
        assert p1.zones[Zone.HAND].contains(filler)

    def test_no_trigger_without_creature_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wardens)
        wardens.register_triggers(game)
        game.active_player_index = 0
        game.creature_died_this_turn = False
        life_before = p1.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p1.life == life_before

    def test_active_player_guard(self) -> None:
        """Only triggers on controller's end step."""
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wardens)
        wardens.register_triggers(game)
        game.active_player_index = 1
        game.creature_died_this_turn = True
        life_before = p1.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p1.life == life_before
