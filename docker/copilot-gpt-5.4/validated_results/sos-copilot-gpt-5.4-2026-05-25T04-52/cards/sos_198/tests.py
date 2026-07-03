"""Tests for SOS 198 — Kirol, History Buff // Pack a Punch."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_198.card_impl import KirolHistoryBuffPackAPunch
from benchmarks.sos.workspace.engine.casting import CastingError, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, Phase, Supertype, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestKirolHistoryBuffPackAPunchProperties:
    """Static front-face data should match the SOS 198 spec."""

    def test_is_legendary_vampire_cleric_creature(self) -> None:
        card = KirolHistoryBuffPackAPunch(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Vampire" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = KirolHistoryBuffPackAPunch(owner=None)

        assert card.name == "Kirol, History Buff"
        assert card.mana_cost == ManaCost.parse("{R}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestKirolHistoryBuffPackAPunchPrepared:
    """Kirol should become prepared when cards leave your graveyard."""

    def test_registers_a_graveyard_leaves_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is GraveyardLeavesTriggeredEvent

    def test_one_or_more_cards_leaving_your_graveyard_puts_a_trigger_on_the_stack_and_prepares_kirol(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            GraveyardLeavesTriggeredEvent(
                player=p1,
                cards=[Sorcery(name="First"), Sorcery(name="Second")],
                destination=Zone.EXILE,
            ),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.is_prepared is True

    def test_opponents_graveyard_leaving_does_not_prepare_kirol(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            GraveyardLeavesTriggeredEvent(
                player=p2,
                cards=[Sorcery(name="Opponent Lesson")],
                destination=Zone.HAND,
            ),
        )

        assert game.stack.is_empty()
        assert card.is_prepared is False

    def test_prepared_spell_copy_is_pack_a_punch_and_unprepares_the_card(self) -> None:
        game = create_game()
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        p1 = game.players[0]
        card = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Pack a Punch"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{1}{R}{W}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KirolHistoryBuffPackAPunch(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="Kirol, History Buff.*not prepared"):
            card.cast_prepared_spell_copy(game)

