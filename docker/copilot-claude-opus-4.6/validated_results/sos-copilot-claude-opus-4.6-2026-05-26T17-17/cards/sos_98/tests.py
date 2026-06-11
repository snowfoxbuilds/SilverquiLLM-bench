"""Tests for SOS 98 — Scathing Shadelock // Venomous Words.

Front face: {4}{B} Creature — Snake Warlock 4/6
At the beginning of your first main phase, this creature becomes prepared.
(While prepared, you may cast a copy of its spell side. Doing so unprepares it.)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_98.card_impl import ScathingShadelock
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestScathingShadelockProperties:
    """Static card data should match the SOS 98 spec."""

    def test_name(self) -> None:
        card = ScathingShadelock(owner=None)
        assert card.name == "Scathing Shadelock"

    def test_mana_cost(self) -> None:
        card = ScathingShadelock(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{B}")

    def test_is_creature(self) -> None:
        card = ScathingShadelock(owner=None)
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = ScathingShadelock(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 6


class TestScathingShadelockPrepared:
    """The prepared mechanic should trigger at the beginning of first main phase."""

    def test_starts_unprepared(self) -> None:
        card = ScathingShadelock(owner=None)
        assert card.prepared is False

    def test_becomes_prepared_at_first_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ScathingShadelock(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Trigger the beginning of first main phase
        card.on_phase_trigger(game, "first_main")
        assert card.prepared is True

    def test_casting_spell_copy_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ScathingShadelock(owner=p1, controller=p1)
        card.prepared = True
        game.get_battlefield(p1).add(card)

        # Cast the spell copy
        card.cast_spell_copy(game)
        assert card.prepared is False

    def test_cannot_cast_spell_copy_when_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ScathingShadelock(owner=p1, controller=p1)
        card.prepared = False
        game.get_battlefield(p1).add(card)

        # Should not be able to cast when unprepared
        assert card.can_cast_spell_copy(game) is False
