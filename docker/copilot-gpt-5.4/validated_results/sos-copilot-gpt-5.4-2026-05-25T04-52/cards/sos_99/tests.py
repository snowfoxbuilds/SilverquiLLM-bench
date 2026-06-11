"""Tests for SOS 99 — Scheming Silvertongue // Sign in Blood."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_99.card_impl import SchemingSilvertongueSignInBlood
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import BeginningOfMainPhaseTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSchemingSilvertongueSignInBloodProperties:
    """Static front-face data should match the SOS 99 spec."""

    def test_is_vampire_warlock_creature_with_flying_and_lifelink(self) -> None:
        card = SchemingSilvertongueSignInBlood(owner=None)
        assert isinstance(card, Creature)
        assert "Vampire" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.LIFELINK in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = SchemingSilvertongueSignInBlood(owner=None)
        assert card.name == "Scheming Silvertongue"
        assert card.mana_cost == ManaCost.parse("{1}{B}")
        assert card.base_power == 1
        assert card.base_toughness == 3


class TestSchemingSilvertongueSignInBloodPrepared:
    """Scheming Silvertongue should use the prepared-state contract."""

    def test_prepared_spell_copy_is_sign_in_blood_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SchemingSilvertongueSignInBlood(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Sign in Blood"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{B}{B}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

class TestSchemingSilvertongueSignInBloodTrigger:
    """Scheming Silvertongue should prepare during your second main phase after enough life gain."""

    def test_registers_a_beginning_of_main_phase_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SchemingSilvertongueSignInBlood(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfMainPhaseTriggeredEvent

    def test_postcombat_main_with_two_life_gained_puts_a_trigger_on_the_stack_and_prepares_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SchemingSilvertongueSignInBlood(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1.life_gained_this_turn = 2
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.POSTCOMBAT_MAIN),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.is_prepared is True
