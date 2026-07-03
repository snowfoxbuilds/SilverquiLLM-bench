"""Tests for SOS 67 — Skycoach Conductor // All Aboard."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_67.card_impl import SkycoachConductorAllAboard
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSkycoachConductorAllAboardProperties:
    """Static front-face data should match the SOS 67 spec."""

    def test_is_bird_pilot_creature_with_flash_flying_and_vigilance(self) -> None:
        card = SkycoachConductorAllAboard(owner=None)
        assert isinstance(card, Creature)
        assert "Bird" in card.subtypes
        assert "Pilot" in card.subtypes
        assert Keyword.FLASH in card.keywords
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = SkycoachConductorAllAboard(owner=None)
        assert card.name == "Skycoach Conductor"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestSkycoachConductorAllAboardPrepared:
    """Skycoach Conductor should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkycoachConductorAllAboard(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_all_aboard_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkycoachConductorAllAboard(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "All Aboard"
        assert isinstance(stack_obj.source, Instant)
        assert stack_obj.source.mana_cost == ManaCost.parse("{U}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkycoachConductorAllAboard(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
