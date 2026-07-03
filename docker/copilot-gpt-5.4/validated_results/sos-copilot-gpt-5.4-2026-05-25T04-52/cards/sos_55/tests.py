"""Tests for SOS 55 — Jadzi, Steward of Fate // Oracle's Gift."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_55.card_impl import JadziStewardOfFateOraclesGift
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestJadziStewardOfFateOraclesGiftProperties:
    """Static front-face data should match the SOS 55 spec."""

    def test_is_legendary_human_wizard_creature(self) -> None:
        card = JadziStewardOfFateOraclesGift(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = JadziStewardOfFateOraclesGift(owner=None)
        assert card.name == "Jadzi, Steward of Fate"
        assert card.mana_cost == ManaCost.parse("{2}{U}")
        assert card.base_power == 2
        assert card.base_toughness == 4


class TestJadziStewardOfFateOraclesGiftPrepared:
    """Jadzi should enter prepared and create Oracle's Gift copies."""

    def test_enters_prepared_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.on_resolve(game)

        assert card.is_prepared is True

    def test_prepared_spell_copy_is_oracles_gift_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Oracle's Gift"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{X}{X}{U}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)


class TestJadziStewardOfFateOraclesGiftEtb:
    """Jadzi should draw two cards, then discard two cards, when it enters."""

    def test_on_resolve_draws_two_then_discards_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        keep = CardImpl(name="Keep Studying", owner=p1, controller=p1)
        draw_one = CardImpl(name="First Lesson", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Lesson", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[], hand=[keep], graveyard=[])
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        p1._script.append(draw_two)
        p1._script.append(keep)

        card = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)
        card.on_resolve(game)

        assert card.is_prepared is True
        assert game.get_hand(p1).contains(draw_one)
        assert not game.get_hand(p1).contains(keep)
        assert not game.get_hand(p1).contains(draw_two)
        assert game.get_graveyard(p1).contains(keep)
        assert game.get_graveyard(p1).contains(draw_two)
