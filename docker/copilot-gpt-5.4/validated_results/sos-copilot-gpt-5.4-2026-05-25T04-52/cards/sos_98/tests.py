"""Tests for SOS 98 — Scathing Shadelock // Venomous Words."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_98.card_impl import ScathingShadelockVenomousWords
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import BeginningOfFirstMainPhaseTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestScathingShadelockVenomousWordsProperties:
    """Static front-face data should match the SOS 98 spec."""

    def test_is_snake_warlock_creature(self) -> None:
        card = ScathingShadelockVenomousWords(owner=None)
        assert isinstance(card, Creature)
        assert "Snake" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = ScathingShadelockVenomousWords(owner=None)
        assert card.name == "Scathing Shadelock"
        assert card.mana_cost == ManaCost.parse("{4}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 6


class TestScathingShadelockVenomousWordsPrepared:
    """Scathing Shadelock should use the prepared-state contract."""

    def test_prepared_spell_copy_is_venomous_words_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ScathingShadelockVenomousWords(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Venomous Words"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{B}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

class TestScathingShadelockVenomousWordsTrigger:
    """Scathing Shadelock should prepare at the beginning of your first main phase."""

    def test_registers_a_beginning_of_first_main_phase_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ScathingShadelockVenomousWords(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfFirstMainPhaseTriggeredEvent

    def test_your_first_main_phase_puts_a_trigger_on_the_stack_and_prepares_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ScathingShadelockVenomousWords(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfFirstMainPhaseTriggeredEvent(player=p1))

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.is_prepared is True
