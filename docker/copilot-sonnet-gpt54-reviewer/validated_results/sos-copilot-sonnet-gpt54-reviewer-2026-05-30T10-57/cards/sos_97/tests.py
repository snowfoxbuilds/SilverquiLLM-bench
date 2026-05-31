"""Tests for sos_97 — Ral Zarek, Guest Lecturer (Planeswalker)."""
from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game


def _populate_library(player, count: int = 10) -> None:
    for i in range(count):
        player.zones[Zone.LIBRARY].add(CardImpl(name=f"Card{i}", owner=player))


class TestRalZarekProperties:
    def test_is_planeswalker(self) -> None:
        from engine.card import Planeswalker
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral Zarek" in card.name

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty_three(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes


class TestRalZarekSurveil:
    """[+1]: Surveil 2 — look at top 2 cards, put any into graveyard."""

    def test_plus_one_increases_loyalty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        _populate_library(p1)
        card.activate_plus_one(game)
        assert card.loyalty == 4

    def test_plus_one_surveil_2_moves_cards_seen_to_graveyard_or_keeps(self) -> None:
        """After surveil 2, top 2 cards are peeked (total cards preserved)."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        _populate_library(p1, count=5)
        initial_lib_size = len(p1.zones[Zone.LIBRARY].get_all())
        card.activate_plus_one(game)
        lib_size = len(p1.zones[Zone.LIBRARY].get_all())
        gy_size = len(p1.zones[Zone.GRAVEYARD].get_all())
        # Cards peeked are either still in library or in graveyard.
        assert lib_size + gy_size == initial_lib_size


class TestRalZarekMinusOne:
    """[-1]: Any number of target players each discard a card."""

    def test_minus_one_decreases_loyalty(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3
        # Add cards to hand so discard works.
        card2 = CardImpl(name="HandCard", owner=p2)
        p2.zones[Zone.HAND].add(card2)
        card.activate_minus_one(game, targets=[p2])
        assert card.loyalty == 2

    def test_minus_one_target_discards_card(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        hand_card = CardImpl(name="HandCard", owner=p2)
        p2.zones[Zone.HAND].add(hand_card)
        card.activate_minus_one(game, targets=[p2])
        assert hand_card not in p2.zones[Zone.HAND].get_all()

    def test_minus_one_multiple_targets_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3
        for player in [p1, p2]:
            c = CardImpl(name=f"Card{player}", owner=player)
            player.zones[Zone.HAND].add(c)
        card.activate_minus_one(game, targets=[p1, p2])
        assert len(p1.zones[Zone.HAND].get_all()) == 0
        assert len(p2.zones[Zone.HAND].get_all()) == 0


class TestRalZarekMinusTwo:
    """[-2]: Return target creature with MV ≤ 3 from graveyard to battlefield."""

    def test_minus_two_decreases_loyalty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 4
        target = Creature(name="Grizzly Bears", base_power=2, base_toughness=2,
                          mana_cost=ManaCost.parse("{1}{G}"), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        card.activate_minus_two(game, target=target)
        assert card.loyalty == 2

    def test_minus_two_returns_creature_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 4
        target = Creature(name="Memnite", base_power=1, base_toughness=1,
                          mana_cost=ManaCost.parse("{0}"), owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        card.activate_minus_two(game, target=target)
        assert target in game.get_battlefield(p1).get_all()
        assert target not in p1.zones[Zone.GRAVEYARD].get_all()


class TestRalZarekMinusSeven:
    """[-7]: Flip 5 coins. Opponent skips X turns (X = heads count)."""

    def test_minus_seven_decreases_loyalty(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 10
        card.activate_minus_seven(game, opponent=p2)
        assert card.loyalty == 3

    def test_minus_seven_sets_skipped_turns(self) -> None:
        """Opponent gains turns_to_skip attribute."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 10
        # Force deterministic coin flips by patching.
        card.activate_minus_seven(game, opponent=p2, forced_heads=3)
        assert getattr(p2, "turns_to_skip", 0) == 3
