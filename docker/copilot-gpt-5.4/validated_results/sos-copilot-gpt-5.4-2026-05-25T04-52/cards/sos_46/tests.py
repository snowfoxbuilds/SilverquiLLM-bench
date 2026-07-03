"""Tests for SOS 46 — Encouraging Aviator // Jump."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_46.card_impl import EncouragingAviatorJump
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, declare_attackers, set_board_state


class TestEncouragingAviatorJumpProperties:
    """Static front-face data should match the SOS 46 spec."""

    def test_is_bird_wizard_creature_with_flying(self) -> None:
        card = EncouragingAviatorJump(owner=None)
        assert isinstance(card, Creature)
        assert "Bird" in card.subtypes
        assert "Wizard" in card.subtypes
        assert Keyword.FLYING in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = EncouragingAviatorJump(owner=None)
        assert card.name == "Encouraging Aviator"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestEncouragingAviatorJumpPrepared:
    """Encouraging Aviator should use the prepared-state contract after attacking."""

    def test_prepared_spell_copy_is_jump_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Jump"
        assert isinstance(stack_obj.source, Instant)
        assert stack_obj.source.mana_cost == ManaCost.parse("{U}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)


class TestEncouragingAviatorJumpAttackTrigger:
    """Encouraging Aviator should become prepared when it attacks."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attack_trigger_puts_a_trigger_on_the_stack_and_prepares_it_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EncouragingAviatorJump(owner=p1, controller=p1)
        card.summoning_sick = False

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        declare_attackers(game, ["Encouraging Aviator"])

        assert len(game.stack) == 1
        assert game.stack.peek().source is card

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert card.is_prepared is True
