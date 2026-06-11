"""Tests for SOS 152 — Infirmary Healer // Stream of Life."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_152.card_impl import InfirmaryHealerStreamOfLife
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestInfirmaryHealerStreamOfLifeProperties:
    """Static front-face data should match the SOS 152 spec."""

    def test_is_cat_cleric_creature(self) -> None:
        card = InfirmaryHealerStreamOfLife(owner=None)

        assert isinstance(card, Creature)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = InfirmaryHealerStreamOfLife(owner=None)

        assert card.name == "Infirmary Healer"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestInfirmaryHealerStreamOfLifePrepared:
    """Infirmary Healer should use the prepared-state contract."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfirmaryHealerStreamOfLife(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_stream_of_life_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfirmaryHealerStreamOfLife(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Stream of Life"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{X}{G}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InfirmaryHealerStreamOfLife(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
