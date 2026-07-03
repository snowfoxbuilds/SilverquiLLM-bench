"""Tests for SOS 88 — Leech Collector // Bloodletting."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_88.card_impl import LeechCollectorBloodletting
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestLeechCollectorBloodlettingProperties:
    """Static front-face data should match the SOS 88 spec."""

    def test_is_human_warlock_creature(self) -> None:
        card = LeechCollectorBloodletting(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = LeechCollectorBloodletting(owner=None)
        assert card.name == "Leech Collector"
        assert card.mana_cost == ManaCost.parse("{1}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestLeechCollectorBloodlettingPrepared:
    """Leech Collector should use the prepared-state contract."""

    def test_prepared_spell_copy_is_bloodletting_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LeechCollectorBloodletting(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Bloodletting"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{B}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card


class TestLeechCollectorBloodlettingLifeGainTrigger:
    """Leech Collector should prepare on the first life gain each turn."""

    def test_registers_a_gains_life_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LeechCollectorBloodletting(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is GainsLifeTriggeredEvent for trigger in triggers)

    def test_first_life_gain_of_your_turn_puts_a_trigger_on_the_stack_and_prepares_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LeechCollectorBloodletting(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.is_prepared is True

    def test_second_life_gain_in_the_same_turn_does_not_prepare_it_again(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LeechCollectorBloodletting(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))
        resolve_top(game)
        assert card.is_prepared is True

        card.become_unprepared()
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))

        assert game.stack.is_empty()
        assert card.is_prepared is False

    def test_first_life_gain_on_an_opponents_turn_still_prepares_it_for_that_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LeechCollectorBloodletting(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.turn_number += 1
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=1))

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.is_prepared is True
