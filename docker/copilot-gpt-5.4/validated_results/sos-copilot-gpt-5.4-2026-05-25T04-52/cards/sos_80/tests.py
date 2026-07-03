"""Tests for SOS 80 — Emeritus of Woe // Demonic Tutor."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_80.card_impl import EmeritusOfWoeDemonicTutor
from benchmarks.sos.workspace.engine.casting import CastingError, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEmeritusOfWoeDemonicTutorProperties:
    """Static front-face data should match the SOS 80 spec."""

    def test_is_vampire_warlock_creature(self) -> None:
        card = EmeritusOfWoeDemonicTutor(owner=None)
        assert isinstance(card, Creature)
        assert "Vampire" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = EmeritusOfWoeDemonicTutor(owner=None)
        assert card.name == "Emeritus of Woe"
        assert card.mana_cost == ManaCost.parse("{3}{B}")
        assert card.base_power == 5
        assert card.base_toughness == 4


class TestEmeritusOfWoeDemonicTutorPrepared:
    """Emeritus of Woe should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_demonic_tutor_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Demonic Tutor"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{1}{B}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)


class TestEmeritusOfWoeDemonicTutorEndStepTrigger:
    """Emeritus of Woe should become prepared after enough creatures die."""

    def test_registers_an_end_step_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is EndStepTriggeredEvent for trigger in triggers)

    def test_your_end_step_after_two_creatures_die_puts_a_trigger_on_the_stack_and_prepares_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        friendly = Creature(
            name="Frail Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing = Creature(
            name="Opposing Assistant",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, friendly])
        set_board_state(game, 1, battlefield=[opposing])
        card.on_resolve(game)
        card.become_unprepared()
        card.register_triggers(game)

        destroy(game, friendly)
        destroy(game, opposing)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.is_prepared is True

    def test_does_not_trigger_when_fewer_than_two_creatures_died_this_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        friendly = Creature(
            name="Frail Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, friendly])
        card.on_resolve(game)
        card.become_unprepared()
        card.register_triggers(game)

        destroy(game, friendly)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert game.stack.is_empty()
        assert card.is_prepared is False

    def test_does_not_trigger_on_an_opponents_end_step_even_if_two_creatures_died(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfWoeDemonicTutor(owner=p1, controller=p1)
        friendly = Creature(
            name="Frail Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing = Creature(
            name="Opposing Assistant",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, friendly])
        set_board_state(game, 1, battlefield=[opposing])
        card.on_resolve(game)
        card.become_unprepared()
        card.register_triggers(game)

        destroy(game, friendly)
        destroy(game, opposing)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p2))

        assert game.stack.is_empty()
        assert card.is_prepared is False
