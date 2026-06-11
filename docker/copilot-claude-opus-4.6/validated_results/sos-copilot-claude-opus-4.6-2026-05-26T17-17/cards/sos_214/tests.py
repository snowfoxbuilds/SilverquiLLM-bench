"""Tests for SOS 214 — Professor Dellian Fel.

Legendary Planeswalker — Dellian {2}{B}{G}
Starting loyalty: 5
+2: You gain 3 life.
0: You draw a card and lose 1 life.
−3: Destroy target creature.
−6: You get an emblem with "Whenever you gain life, target opponent loses that much life."
"""

from __future__ import annotations

import pytest

from cards.sos.sos_214.card_impl import ProfessorDellianFel
from engine.card import Planeswalker, Creature
from engine.types import ManaCost
from test_utils import create_game, set_board_state


class TestProfessorDellianFelProperties:
    """Static card data should match the SOS 214 spec."""

    def test_is_planeswalker(self) -> None:
        assert isinstance(ProfessorDellianFel(owner=None), Planeswalker)

    def test_name(self) -> None:
        assert ProfessorDellianFel(owner=None).name == "Professor Dellian Fel"

    def test_mana_cost(self) -> None:
        assert ProfessorDellianFel(owner=None).mana_cost == ManaCost.parse("{2}{B}{G}")

    def test_starting_loyalty(self) -> None:
        card = ProfessorDellianFel(owner=None)
        assert card.loyalty == 5

    def test_is_legendary(self) -> None:
        card = ProfessorDellianFel(owner=None)
        assert card.is_legendary is True


class TestProfessorDellianFelPlusTwo:
    """+2: You gain 3 life."""

    def test_plus_two_gains_3_life(self) -> None:
        game = create_game()
        p1 = game.players[0]

        pw = ProfessorDellianFel(owner=p1, controller=p1)
        pw.loyalty = 5
        game.get_battlefield(p1).add(pw)

        pw.activate_loyalty_ability(game, 0)  # +2 ability

        assert p1.life == 23  # 20 + 3
        assert pw.loyalty == 7  # 5 + 2


class TestProfessorDellianFelZero:
    """0: You draw a card and lose 1 life."""

    def test_zero_draws_card_and_loses_life(self) -> None:
        game = create_game()
        p1 = game.players[0]

        pw = ProfessorDellianFel(owner=p1, controller=p1)
        pw.loyalty = 5
        game.get_battlefield(p1).add(pw)

        # Put a card in library to draw
        dummy = Creature(name="Drawn Card", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).append(dummy)

        hand_before = len(game.get_hand(p1))
        pw.activate_loyalty_ability(game, 1)  # 0 ability

        assert len(game.get_hand(p1)) == hand_before + 1
        assert p1.life == 19  # 20 - 1
        assert pw.loyalty == 5  # unchanged (0 cost)


class TestProfessorDellianFelMinusThree:
    """−3: Destroy target creature."""

    def test_minus_three_destroys_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        pw = ProfessorDellianFel(owner=p1, controller=p1)
        pw.loyalty = 5
        game.get_battlefield(p1).add(pw)

        target = Creature(
            name="Doomed Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p2).add(target)

        pw.activate_loyalty_ability(game, 2, targets=[target])  # -3 ability

        assert target not in game.get_battlefield(p2)
        assert target in game.get_graveyard(p2)
        assert pw.loyalty == 2  # 5 - 3


class TestProfessorDellianFelMinusSix:
    """−6: Emblem — Whenever you gain life, target opponent loses that much life."""

    def test_minus_six_creates_emblem(self) -> None:
        game = create_game()
        p1 = game.players[0]

        pw = ProfessorDellianFel(owner=p1, controller=p1)
        pw.loyalty = 6
        game.get_battlefield(p1).add(pw)

        pw.activate_loyalty_ability(game, 3)  # -6 ability

        assert pw.loyalty == 0
        # Player should have an emblem
        assert len(p1.emblems) >= 1

    def test_emblem_drains_opponent_on_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        pw = ProfessorDellianFel(owner=p1, controller=p1)
        pw.loyalty = 6
        game.get_battlefield(p1).add(pw)

        pw.activate_loyalty_ability(game, 3)  # create emblem

        # Now gain life — opponent should lose that much
        p1.gain_life(game, 3)
        assert p2.life == 17  # 20 - 3
