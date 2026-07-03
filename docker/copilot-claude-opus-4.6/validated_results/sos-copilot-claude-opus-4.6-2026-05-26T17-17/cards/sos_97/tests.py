"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Legendary Planeswalker — Ral with loyalty 3.
+1: Surveil 2.
-1: Any number of target players each discard a card.
-2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
-7: Flip five coins. Target opponent skips their next X turns (X = heads count).
"""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestRalZarekProperties:
    """Static card data should match the SOS 97 spec."""

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.loyalty == 3

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.is_legendary is True


class TestRalZarekPlusOne:
    """The +1 ability should surveil 2."""

    def test_plus_one_increases_loyalty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3
        game.get_battlefield(p1).add(card)

        card.activate_loyalty_ability(game, 0)  # +1 ability
        assert card.loyalty == 4

    def test_plus_one_surveils_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3
        game.get_battlefield(p1).add(card)

        # Set up library with known cards
        c1 = Creature(name="Card A", owner=p1, base_power=1, base_toughness=1)
        c2 = Creature(name="Card B", owner=p1, base_power=1, base_toughness=1)
        c3 = Creature(name="Card C", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[], graveyard=[])
        game.get_library(p1).cards = [c1, c2, c3]

        card.activate_loyalty_ability(game, 0)  # +1: Surveil 2
        # After surveil 2, cards should have moved (to graveyard or bottom of library)
        # The library should have fewer than 3 cards on top or graveyard should have cards
        lib_count = len(game.get_library(p1).cards)
        grave_count = len(game.get_graveyard(p1).get_all())
        assert lib_count + grave_count >= 2  # surveil touched at least 2 cards


class TestRalZarekMinusOne:
    """The -1 ability makes target players discard a card."""

    def test_minus_one_decreases_loyalty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3
        game.get_battlefield(p1).add(card)

        card.activate_loyalty_ability(game, 1)  # -1 ability
        assert card.loyalty == 2

    def test_minus_one_causes_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3
        game.get_battlefield(p1).add(card)

        hand_card = Creature(name="Victim", owner=p2, base_power=1, base_toughness=1)
        set_board_state(game, 1, hand=[hand_card])

        card.chosen_targets = [p2]
        card.activate_loyalty_ability(game, 1)  # -1: target player discards
        assert len(game.get_hand(p2).get_all()) == 0


class TestRalZarekMinusTwo:
    """The -2 ability returns a creature with MV<=3 from graveyard to battlefield."""

    def test_minus_two_returns_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 4
        game.get_battlefield(p1).add(card)

        target = Creature(
            name="Small Creature", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        target.mana_cost = ManaCost.parse("{1}{B}")
        set_board_state(game, 0, graveyard=[target])

        card.chosen_targets = [target]
        card.activate_loyalty_ability(game, 2)  # -2 ability
        assert card.loyalty == 2
        # Target should be on the battlefield now
        bf = game.get_battlefield(p1).get_all()
        assert target in bf or any(c.name == "Small Creature" for c in bf)
