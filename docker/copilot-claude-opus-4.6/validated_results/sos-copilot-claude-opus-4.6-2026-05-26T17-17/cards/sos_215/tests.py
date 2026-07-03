"""Tests for SOS 215 — Pterafractyl.

Creature — Dinosaur Fractal {X}{G}{U}
1/0
Flying
This creature enters with X +1/+1 counters on it.
When this creature enters, you gain 2 life.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_215.card_impl import Pterafractyl
from engine.card import Creature
from engine.types import Keyword, ManaCost
from test_utils import create_game, set_board_state


class TestPterafractylProperties:
    """Static card data should match the SOS 215 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(Pterafractyl(owner=None), Creature)

    def test_name(self) -> None:
        assert Pterafractyl(owner=None).name == "Pterafractyl"

    def test_mana_cost(self) -> None:
        assert Pterafractyl(owner=None).mana_cost == ManaCost.parse("{X}{G}{U}")

    def test_base_power_toughness(self) -> None:
        card = Pterafractyl(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 0

    def test_has_flying(self) -> None:
        card = Pterafractyl(owner=None)
        assert Keyword.FLYING in card.keywords


class TestPterafractylEntersWithCounters:
    """This creature enters with X +1/+1 counters on it."""

    def test_enters_with_x_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = Pterafractyl(owner=p1, controller=p1)
        card.x_value = 3
        card.on_enter_battlefield(game)

        assert card.plus_one_counters == 3

    def test_enters_with_zero_counters_when_x_is_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = Pterafractyl(owner=p1, controller=p1)
        card.x_value = 0
        card.on_enter_battlefield(game)

        assert card.plus_one_counters == 0

    def test_effective_power_includes_counters(self) -> None:
        """With X=3, effective power should be 1 + 3 = 4."""
        game = create_game()
        p1 = game.players[0]

        card = Pterafractyl(owner=p1, controller=p1)
        card.x_value = 3
        card.on_enter_battlefield(game)

        assert card.power == 4  # base 1 + 3 counters
        assert card.toughness == 3  # base 0 + 3 counters


class TestPterafractylLifeGain:
    """When this creature enters, you gain 2 life."""

    def test_gains_2_life_on_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = Pterafractyl(owner=p1, controller=p1)
        card.x_value = 2
        card.on_enter_battlefield(game)

        assert p1.life == 22  # 20 + 2

    def test_life_gain_happens_regardless_of_x(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = Pterafractyl(owner=p1, controller=p1)
        card.x_value = 0
        card.on_enter_battlefield(game)

        assert p1.life == 22  # still gains 2 life
