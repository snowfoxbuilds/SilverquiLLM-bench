"""Tests for SOS 99 — Scheming Silvertongue // Sign in Blood.

Front face: {1}{B} Creature — Vampire Warlock 1/3
Flying, lifelink
At the beginning of your second main phase, if you gained 2 or more life
this turn, this creature becomes prepared.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_99.card_impl import SchemingSilvertongue
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSchemingSilvertongueProperties:
    """Static card data should match the SOS 99 spec."""

    def test_name(self) -> None:
        card = SchemingSilvertongue(owner=None)
        assert card.name == "Scheming Silvertongue"

    def test_mana_cost(self) -> None:
        card = SchemingSilvertongue(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")

    def test_is_creature(self) -> None:
        card = SchemingSilvertongue(owner=None)
        assert isinstance(card, Creature)

    def test_power_toughness(self) -> None:
        card = SchemingSilvertongue(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = SchemingSilvertongue(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_lifelink(self) -> None:
        card = SchemingSilvertongue(owner=None)
        assert Keyword.LIFELINK in card.keywords


class TestSchemingSilvertonguePrepared:
    """Becomes prepared at second main phase if 2+ life gained this turn."""

    def test_starts_unprepared(self) -> None:
        card = SchemingSilvertongue(owner=None)
        assert card.prepared is False

    def test_becomes_prepared_with_sufficient_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SchemingSilvertongue(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Simulate gaining 2+ life this turn
        game.life_gained_this_turn = {p1: 2}
        card.on_phase_trigger(game, "second_main")
        assert card.prepared is True

    def test_does_not_prepare_with_insufficient_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SchemingSilvertongue(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Only 1 life gained — not enough
        game.life_gained_this_turn = {p1: 1}
        card.on_phase_trigger(game, "second_main")
        assert card.prepared is False

    def test_does_not_prepare_with_no_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SchemingSilvertongue(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        game.life_gained_this_turn = {p1: 0}
        card.on_phase_trigger(game, "second_main")
        assert card.prepared is False
