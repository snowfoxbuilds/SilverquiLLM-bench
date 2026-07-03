"""Tests for SOS 58 — Mathemagics."""

from __future__ import annotations

import pytest

from cards.sos.sos_58.card_impl import Mathemagics
from engine.card import Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestMathemagicsProperties:
    """Static card data should match the SOS 58 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(Mathemagics(owner=None), Sorcery)

    def test_name(self) -> None:
        assert Mathemagics(owner=None).name == "Mathemagics"

    def test_mana_cost(self) -> None:
        assert Mathemagics(owner=None).mana_cost == ManaCost.parse("{X}{X}{U}{U}")


class TestMathemagicsDrawEffect:
    """Target player draws 2^X cards."""

    def test_x_equals_0_draws_1_card(self) -> None:
        """2^0 = 1, so player draws 1 card."""
        game = create_game()
        p1 = game.players[0]

        # Give player some cards in library
        set_board_state(game, 0, mana={ManaType.BLUE: 2})
        initial_hand = len(game.get_hand(p1))

        spell = Mathemagics(owner=p1, controller=p1)
        spell.x_value = 0
        spell.chosen_targets = [p1]
        spell.on_resolve(game)

        assert len(game.get_hand(p1)) == initial_hand + 1

    def test_x_equals_1_draws_2_cards(self) -> None:
        """2^1 = 2, so player draws 2 cards."""
        game = create_game()
        p1 = game.players[0]
        initial_hand = len(game.get_hand(p1))

        spell = Mathemagics(owner=p1, controller=p1)
        spell.x_value = 1
        spell.chosen_targets = [p1]
        spell.on_resolve(game)

        assert len(game.get_hand(p1)) == initial_hand + 2

    def test_x_equals_2_draws_4_cards(self) -> None:
        """2^2 = 4, so player draws 4 cards."""
        game = create_game()
        p1 = game.players[0]
        initial_hand = len(game.get_hand(p1))

        spell = Mathemagics(owner=p1, controller=p1)
        spell.x_value = 2
        spell.chosen_targets = [p1]
        spell.on_resolve(game)

        assert len(game.get_hand(p1)) == initial_hand + 4

    def test_x_equals_3_draws_8_cards(self) -> None:
        """2^3 = 8, so player draws 8 cards."""
        game = create_game()
        p1 = game.players[0]
        initial_hand = len(game.get_hand(p1))

        spell = Mathemagics(owner=p1, controller=p1)
        spell.x_value = 3
        spell.chosen_targets = [p1]
        spell.on_resolve(game)

        assert len(game.get_hand(p1)) == initial_hand + 8

    def test_can_target_opponent(self) -> None:
        """Target player can be the opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        initial_hand = len(game.get_hand(p2))

        spell = Mathemagics(owner=p1, controller=p1)
        spell.x_value = 1
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert len(game.get_hand(p2)) == initial_hand + 2
