"""Tests for SOS 109 — Blazing Firesinger // Seething Song."""

from __future__ import annotations

import pytest

from cards.sos.sos_109.card_impl import BlazingFiresinger
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestBlazingFiresingerProperties:
    """Static card data should match SOS 109 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(BlazingFiresinger(owner=None), Creature)

    def test_name(self) -> None:
        assert BlazingFiresinger(owner=None).name == "Blazing Firesinger"

    def test_mana_cost(self) -> None:
        assert BlazingFiresinger(owner=None).mana_cost == ManaCost.parse("{2}{R}")

    def test_power_toughness(self) -> None:
        card = BlazingFiresinger(owner=None)
        assert card.power == 2
        assert card.toughness == 3


class TestBlazingFiresingerPrepared:
    """Blazing Firesinger enters prepared and can cast its spell side."""

    def test_enters_prepared(self) -> None:
        """When entering the battlefield, the creature should be prepared."""
        game = create_game()
        p1 = game.players[0]
        card = BlazingFiresinger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.prepared is True

    def test_has_prepared_keyword(self) -> None:
        card = BlazingFiresinger(owner=None)
        assert Keyword.PREPARED in card.keywords

    def test_casting_spell_unprepares(self) -> None:
        """Using the prepared ability unprepares the creature."""
        game = create_game()
        p1 = game.players[0]
        card = BlazingFiresinger(owner=p1, controller=p1)
        card.prepared = True
        game.get_battlefield(p1).add(card)
        card.cast_prepared_spell(game)
        assert card.prepared is False

    def test_cannot_cast_when_unprepared(self) -> None:
        """Cannot cast the spell if already unprepared."""
        game = create_game()
        p1 = game.players[0]
        card = BlazingFiresinger(owner=p1, controller=p1)
        card.prepared = False
        game.get_battlefield(p1).add(card)
        # Should not be able to activate
        assert card.can_cast_prepared_spell(game) is False
