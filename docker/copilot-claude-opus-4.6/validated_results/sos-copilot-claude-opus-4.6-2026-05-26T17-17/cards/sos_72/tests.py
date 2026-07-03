"""Tests for SOS 72 — Adventurous Eater // Have a Bite."""

from __future__ import annotations

import pytest

from cards.sos.sos_72.card_impl import AdventurousEater
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestAdventurousEaterProperties:
    """Static card data should match the SOS 72 spec."""

    def test_is_creature(self) -> None:
        card = AdventurousEater(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert AdventurousEater(owner=None).name == "Adventurous Eater"

    def test_mana_cost(self) -> None:
        assert AdventurousEater(owner=None).mana_cost == ManaCost.parse("{2}{B}")

    def test_power_toughness(self) -> None:
        card = AdventurousEater(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_has_prepared_keyword(self) -> None:
        card = AdventurousEater(owner=None)
        assert Keyword.PREPARED in card.keywords


class TestAdventurousEaterPrepared:
    """The creature enters prepared and can cast its spell side."""

    def test_enters_battlefield_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdventurousEater(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card],
                        mana={ManaType.BLACK: 3, ManaType.COLORLESS: 2})

        # Simulate entering the battlefield
        card.on_enter_battlefield(game)
        assert card.prepared is True

    def test_casting_spell_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdventurousEater(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.BLACK: 1})
        card.prepared = True

        # Cast the spell side
        card.cast_prepared_spell(game)
        assert card.prepared is False

    def test_cannot_cast_spell_when_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdventurousEater(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.BLACK: 1})
        card.prepared = False

        # Should not be able to cast the spell when not prepared
        assert card.can_cast_prepared_spell(game) is False
