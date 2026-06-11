"""Tests for SOS 166 — Vastlands Scavenger // Bind to Life."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_166.card_impl import VastlandsScavengerBindToLife
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestVastlandsScavengerBindToLifeProperties:
    """Static front-face data should match the SOS 166 spec."""

    def test_is_bear_druid_creature_with_deathtouch(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)

        assert isinstance(card, Creature)
        assert "Bear" in card.subtypes
        assert "Druid" in card.subtypes
        assert Keyword.DEATHTOUCH in card.keywords

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)

        assert card.name == "Vastlands Scavenger"
        assert card.mana_cost == ManaCost.parse("{1}{G}{G}")
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestVastlandsScavengerBindToLifePrepared:
    """Vastlands Scavenger should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VastlandsScavengerBindToLife(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_bind_to_life_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VastlandsScavengerBindToLife(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Bind to Life"
        assert isinstance(stack_obj.source, Instant)
        assert stack_obj.source.mana_cost == ManaCost.parse("{4}{G}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VastlandsScavengerBindToLife(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="Vastlands Scavenger.*not prepared"):
            card.cast_prepared_spell_copy(game)
