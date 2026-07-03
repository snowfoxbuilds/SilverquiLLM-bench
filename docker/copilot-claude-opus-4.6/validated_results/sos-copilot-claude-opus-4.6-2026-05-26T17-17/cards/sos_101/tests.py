"""Tests for SOS 101 — Sneering Shadewriter.

A 3/3 Flying Vampire Warlock for {4}{B}.
ETB: each opponent loses 2 life and you gain 2 life.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_101.card_impl import SneeringShadewriter
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSneeringShadewriterProperties:
    """Static card data should match the SOS 101 spec."""

    def test_is_creature(self) -> None:
        card = SneeringShadewriter(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert SneeringShadewriter(owner=None).name == "Sneering Shadewriter"

    def test_mana_cost(self) -> None:
        assert SneeringShadewriter(owner=None).mana_cost == ManaCost.parse("{4}{B}")

    def test_power_and_toughness(self) -> None:
        card = SneeringShadewriter(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = SneeringShadewriter(owner=None)
        assert Keyword.FLYING in card.keywords


class TestSneeringShadewriterETB:
    """ETB trigger: each opponent loses 2 life and you gain 2 life."""

    def test_opponent_loses_2_life_on_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SneeringShadewriter(owner=p1, controller=p1)
        set_board_state(game, 0, mana={ManaType.BLACK: 1, ManaType.COLORLESS: 4})

        # Simulate ETB trigger
        card.on_enter_battlefield(game)

        assert p2.life == 18  # lost 2

    def test_controller_gains_2_life_on_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SneeringShadewriter(owner=p1, controller=p1)

        card.on_enter_battlefield(game)

        assert p1.life == 22  # gained 2

    def test_etb_drain_both_effects_together(self) -> None:
        game = create_game(player1_life=10, player2_life=10)
        p1 = game.players[0]
        p2 = game.players[1]
        card = SneeringShadewriter(owner=p1, controller=p1)

        card.on_enter_battlefield(game)

        assert p1.life == 12
        assert p2.life == 8
