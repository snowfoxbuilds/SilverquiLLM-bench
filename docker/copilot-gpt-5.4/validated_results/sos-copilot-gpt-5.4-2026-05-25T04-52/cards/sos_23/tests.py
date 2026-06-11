"""Tests for SOS 23 — Joined Researchers // Secret Rendezvous."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_23.card_impl import JoinedResearchersSecretRendezvous
from benchmarks.sos.workspace.engine.casting import CastingError, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestJoinedResearchersSecretRendezvousProperties:
    """Static front-face data should match the SOS 23 spec."""

    def test_is_human_cleric_wizard_creature_with_first_strike(self) -> None:
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Cleric" in card.subtypes
        assert "Wizard" in card.subtypes
        assert Keyword.FIRST_STRIKE in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert card.name == "Joined Researchers"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestJoinedResearchersSecretRendezvousPrepared:
    """Joined Researchers should become prepared on qualifying end steps."""

    def test_registers_an_end_step_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EndStepTriggeredEvent

    def test_opponents_end_step_with_more_cards_in_hand_puts_trigger_on_stack_and_prepares(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[CardImpl(name="Your Note")],
        )
        set_board_state(
            game,
            1,
            hand=[CardImpl(name="A"), CardImpl(name="B"), CardImpl(name="C")],
        )
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p2))

        assert len(game.stack) == 1
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card.is_prepared is True

    def test_does_not_prepare_when_no_opponent_has_more_cards_in_hand(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[CardImpl(name="Your Note"), CardImpl(name="Second Note")],
        )
        set_board_state(
            game,
            1,
            hand=[CardImpl(name="A"), CardImpl(name="B")],
        )
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p2))

        assert game.stack.is_empty()
        assert card.is_prepared is False

    def test_prepared_spell_copy_is_secret_rendezvous_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Secret Rendezvous"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
