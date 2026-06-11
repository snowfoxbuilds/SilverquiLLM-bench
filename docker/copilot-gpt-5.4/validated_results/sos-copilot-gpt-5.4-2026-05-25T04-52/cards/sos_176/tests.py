"""Tests for SOS 176 — Blech, Loafing Pest."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_176.card_impl import BlechLoafingPest
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestBlechLoafingPestProperties:
    """Static card data should match the SOS 176 spec."""

    def test_is_legendary_pest_creature(self) -> None:
        card = BlechLoafingPest(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Pest" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = BlechLoafingPest(owner=None)

        assert card.name == "Blech, Loafing Pest"
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestBlechLoafingPestLifeGainTrigger:
    """Blech should grow your supported creature tribes when you gain life."""

    def test_registers_a_gains_life_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BlechLoafingPest(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is GainsLifeTriggeredEvent for trigger in triggers)

    def test_gain_life_puts_a_plus_one_plus_one_counter_on_each_supported_creature_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        blech = BlechLoafingPest(owner=p1, controller=p1)
        bat = Creature(
            name="Helpful Bat",
            owner=p1,
            controller=p1,
            subtypes={"Bat"},
            base_power=1,
            base_toughness=1,
        )
        snake_spider = Creature(
            name="Tangle Crawler",
            owner=p1,
            controller=p1,
            subtypes={"Snake", "Spider"},
            base_power=2,
            base_toughness=2,
        )
        frog = Creature(
            name="Ordinary Frog",
            owner=p1,
            controller=p1,
            subtypes={"Frog"},
            base_power=2,
            base_toughness=2,
        )
        opposing_pest = Creature(
            name="Enemy Pest",
            owner=p2,
            controller=p2,
            subtypes={"Pest"},
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[blech, bat, snake_spider, frog])
        set_board_state(game, 1, battlefield=[opposing_pest])
        blech.register_triggers(game)

        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=2))

        assert len(game.stack) == 1

        resolve_top(game)

        assert blech.plus_one_counters == 1
        assert bat.plus_one_counters == 1
        assert snake_spider.plus_one_counters == 1
        assert frog.plus_one_counters == 0
        assert opposing_pest.plus_one_counters == 0

    def test_opponents_life_gain_does_not_trigger_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        blech = BlechLoafingPest(owner=p1, controller=p1)
        pest = Creature(
            name="Helpful Pest",
            owner=p1,
            controller=p1,
            subtypes={"Pest"},
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[blech, pest])
        blech.register_triggers(game)

        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p2, amount=1))

        assert game.stack.is_empty()
        assert blech.plus_one_counters == 0
        assert pest.plus_one_counters == 0
