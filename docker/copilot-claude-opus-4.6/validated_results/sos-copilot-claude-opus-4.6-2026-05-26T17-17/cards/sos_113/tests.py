"""Tests for SOS 113 — Emeritus of Conflict // Lightning Bolt."""

from __future__ import annotations

import pytest

from cards.sos.sos_113.card_impl import EmeritusOfConflict
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestEmeritusOfConflictProperties:
    """Static card data for the front face."""

    def test_is_creature(self) -> None:
        assert isinstance(EmeritusOfConflict(owner=None), Creature)

    def test_name(self) -> None:
        assert EmeritusOfConflict(owner=None).name == "Emeritus of Conflict"

    def test_mana_cost(self) -> None:
        assert EmeritusOfConflict(owner=None).mana_cost == ManaCost.parse("{1}{R}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfConflict(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_first_strike(self) -> None:
        card = EmeritusOfConflict(owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords


class TestEmeritusOfConflictPrepared:
    """Becomes prepared when you cast your third spell each turn."""

    def test_not_prepared_initially(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfConflict(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        assert card.is_prepared is False

    def test_becomes_prepared_after_third_spell(self) -> None:
        """Whenever you cast your third spell each turn, becomes prepared."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfConflict(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Simulate casting three spells
        dummy = Instant(name="Shock", owner=p1, controller=p1)
        card.on_spell_cast(game, p1, spell_number=3)

        assert card.is_prepared is True

    def test_not_prepared_after_only_two_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfConflict(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        card.on_spell_cast(game, p1, spell_number=2)

        assert card.is_prepared is False


class TestEmeritusOfConflictBackFace:
    """The back face is Lightning Bolt."""

    def test_back_face_name(self) -> None:
        card = EmeritusOfConflict(owner=None)
        assert card.back_face_name == "Lightning Bolt"

    def test_back_face_mana_cost(self) -> None:
        card = EmeritusOfConflict(owner=None)
        assert card.back_face_mana_cost == ManaCost.parse("{R}")

    def test_casting_back_face_unprepares(self) -> None:
        """Casting the back face spell unprepares the creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfConflict(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.is_prepared = True

        card.cast_prepared_spell(game)

        assert card.is_prepared is False
