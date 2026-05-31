"""Tests for sos_201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestLoreholdProperties:
    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtypes(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords


class TestLoreholdUpkeepTrigger:
    """At beginning of each opponent's upkeep, may discard → draw."""

    def test_register_triggers_adds_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_upkeep_trigger_condition_false_for_own_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        upkeep_triggers = [t for t in triggers
                           if t.event_type is BeginningOfUpkeepTriggeredEvent]
        assert upkeep_triggers
        trigger = upkeep_triggers[0]
        # Active player is p1 (own upkeep) — condition should be False.
        game.active_player_index = 0
        if trigger.condition is not None:
            assert trigger.condition(game, BeginningOfUpkeepTriggeredEvent()) is False

    def test_upkeep_trigger_condition_true_for_opponents_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        upkeep_triggers = [t for t in triggers
                           if t.event_type is BeginningOfUpkeepTriggeredEvent]
        trigger = upkeep_triggers[0]
        # Active player is p2 (opponent) — condition should be True.
        game.active_player_index = 1
        if trigger.condition is not None:
            assert trigger.condition(game, BeginningOfUpkeepTriggeredEvent()) is True

    def test_discard_draw_loot_effect(self) -> None:
        """When triggered and player says yes, they discard then draw."""
        game = create_game(scripts=[[True, 0], []])  # p1: yes, choose index 0
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_card = Instant(name="Discard Me", owner=p1, controller=p1)
        library_card = Instant(name="Draw Me", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_card])
        p1.zones[Zone.LIBRARY].add(library_card)
        # Reset draw counter.
        p1.cards_drawn_this_turn = 0
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        upkeep_triggers = [t for t in triggers
                           if t.event_type is BeginningOfUpkeepTriggeredEvent]
        upkeep_triggers[0].effect(game)
        assert game.get_graveyard(p1).contains(discard_card)
        assert game.get_hand(p1).contains(library_card)


class TestLoreholdMiracleCost:
    """Miracle cost for instants/sorceries is {2}."""

    def test_miracle_cost_is_two(self) -> None:
        assert LoreholdTheHistorian.get_miracle_cost() == ManaCost.parse("{2}")
