"""Tests for SOS 27 — Quill-Blade Laureate // Twofold Intent."""

from __future__ import annotations

import pytest
from cards.sos.sos_27.card_impl import QuillBladeLaureateTwofoldIntent
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class TestQuillBladeLaureateProperties:
    """Static card data should match the SOS 27 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(QuillBladeLaureateTwofoldIntent(owner=None), Creature)

    def test_name(self) -> None:
        card = QuillBladeLaureateTwofoldIntent(owner=None)
        assert card.name == "Quill-Blade Laureate"

    def test_mana_cost(self) -> None:
        card = QuillBladeLaureateTwofoldIntent(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = QuillBladeLaureateTwofoldIntent(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_double_strike(self) -> None:
        card = QuillBladeLaureateTwofoldIntent(owner=None)
        assert Keyword.DOUBLE_STRIKE in card.keywords


class TestQuillBladeLaureatePrepared:
    """This creature enters prepared. While prepared, you may cast a copy of its spell."""

    def test_enters_battlefield_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = QuillBladeLaureateTwofoldIntent(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Quill-Blade Laureate")
        bf = game.get_battlefield(p1)
        creature = next(c for c in bf if c.name == "Quill-Blade Laureate")
        assert creature.prepared is True

    def test_casting_spell_copy_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = QuillBladeLaureateTwofoldIntent(owner=p1, controller=p1)
        card.prepared = True
        game.get_battlefield(p1).add(card)
        # Cast the spell copy from the prepared creature
        card.cast_prepared_spell(game)
        assert card.prepared is False

    def test_cannot_cast_spell_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = QuillBladeLaureateTwofoldIntent(owner=p1, controller=p1)
        card.prepared = False
        game.get_battlefield(p1).add(card)
        with pytest.raises(Exception):
            card.cast_prepared_spell(game)
