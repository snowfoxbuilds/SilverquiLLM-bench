"""Tests for SOS 160 — Slumbering Trudge."""

from __future__ import annotations

from cards.sos.sos_160.card_impl import SlumberingTrudge
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestSlumberingTrudgeProperties:
    """Static card data should match the SOS 160 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SlumberingTrudge(owner=None), Creature)

    def test_name(self) -> None:
        assert SlumberingTrudge(owner=None).name == "Slumbering Trudge"

    def test_mana_cost(self) -> None:
        assert SlumberingTrudge(owner=None).mana_cost == ManaCost.parse("{X}{G}")

    def test_power_toughness(self) -> None:
        trudge = SlumberingTrudge(owner=None)
        assert trudge.power == 6
        assert trudge.toughness == 6


class TestSlumberingTrudgeStunCounters:
    """Enters with (3 - X) stun counters. If X <= 2, enters tapped."""

    def test_x_equals_zero_gets_three_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 0
        trudge.on_enter_battlefield(game)

        assert trudge.stun_counters == 3

    def test_x_equals_one_gets_two_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 1
        trudge.on_enter_battlefield(game)

        assert trudge.stun_counters == 2

    def test_x_equals_two_gets_one_stun_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 2
        trudge.on_enter_battlefield(game)

        assert trudge.stun_counters == 1

    def test_x_equals_three_gets_zero_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 3
        trudge.on_enter_battlefield(game)

        assert trudge.stun_counters == 0

    def test_x_greater_than_three_gets_zero_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 5
        trudge.on_enter_battlefield(game)

        assert trudge.stun_counters == 0


class TestSlumberingTrudgeEntersTapped:
    """If X is 2 or less, it enters tapped."""

    def test_x_equals_zero_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 0
        trudge.on_enter_battlefield(game)

        assert trudge.tapped is True

    def test_x_equals_two_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 2
        trudge.on_enter_battlefield(game)

        assert trudge.tapped is True

    def test_x_equals_three_enters_untapped(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 3
        trudge.on_enter_battlefield(game)

        assert trudge.tapped is False

    def test_x_equals_five_enters_untapped(self) -> None:
        game = create_game()
        p1 = game.players[0]

        trudge = SlumberingTrudge(owner=p1, controller=p1)
        trudge.x_value = 5
        trudge.on_enter_battlefield(game)

        assert trudge.tapped is False
