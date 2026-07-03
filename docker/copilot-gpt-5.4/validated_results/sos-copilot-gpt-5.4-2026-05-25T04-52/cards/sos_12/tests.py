"""Tests for SOS 12 — Elite Interceptor // Rejoinder."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_12.card_impl import EliteInterceptorRejoinder
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEliteInterceptorRejoinderProperties:
    """Static front-face data should match the SOS 12 spec."""

    def test_is_human_wizard_creature(self) -> None:
        card = EliteInterceptorRejoinder(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = EliteInterceptorRejoinder(owner=None)
        assert card.name == "Elite Interceptor"
        assert card.mana_cost == ManaCost.parse("{W}")
        assert card.base_power == 1
        assert card.base_toughness == 2


class TestEliteInterceptorPrepared:
    """Elite Interceptor should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EliteInterceptorRejoinder(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_can_be_cast_and_unprepares_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EliteInterceptorRejoinder(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Rejoinder"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EliteInterceptorRejoinder(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
