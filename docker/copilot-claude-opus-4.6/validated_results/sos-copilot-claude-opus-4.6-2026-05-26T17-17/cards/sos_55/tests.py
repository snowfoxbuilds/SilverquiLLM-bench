"""Tests for SOS 55 — Jadzi, Steward of Fate // Oracle's Gift."""

from __future__ import annotations

import pytest

from cards.sos.sos_55.card_impl import JadziStewardOfFateOraclesGift
from engine.card import Creature, CardImpl
from engine.types import CardType, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


class TestJadziProperties:
    """Static card data should match the SOS 55 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(JadziStewardOfFateOraclesGift(owner=None), Creature)

    def test_name(self) -> None:
        assert JadziStewardOfFateOraclesGift(owner=None).name == "Jadzi, Steward of Fate"

    def test_mana_cost(self) -> None:
        assert JadziStewardOfFateOraclesGift(owner=None).mana_cost == ManaCost.parse("{2}{U}")

    def test_power_toughness(self) -> None:
        card = JadziStewardOfFateOraclesGift(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        card = JadziStewardOfFateOraclesGift(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = JadziStewardOfFateOraclesGift(owner=None)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes


class TestJadziEntersPrepared:
    """Jadzi enters the battlefield prepared."""

    def test_enters_prepared(self) -> None:
        """When Jadzi enters, it should be prepared."""
        game = create_game()
        p1 = game.players[0]

        jadzi = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[jadzi])

        # Simulate ETB trigger
        jadzi.on_enter_battlefield(game)

        assert getattr(jadzi, "is_prepared", False) is True


class TestJadziETBDrawDiscard:
    """When Jadzi enters, draw two cards then discard two cards."""

    def test_draws_two_cards_on_etb(self) -> None:
        """ETB trigger draws two cards."""
        game = create_game()
        p1 = game.players[0]

        jadzi = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)

        # Put cards in library
        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[], battlefield=[jadzi])
        for card in lib_cards:
            game.get_library(p1).append(card)

        hand_before = len(game.get_hand(p1))
        jadzi.on_enter_battlefield(game)

        # After draw 2, discard 2, net hand change depends on discard
        # But at minimum 2 cards should have been drawn
        # The hand should have net 0 change (draw 2, discard 2)
        # But we want to verify the draw happened
        # We check library decreased by 2
        assert len(game.get_library(p1)) == 3  # started with 5, drew 2

    def test_discards_two_cards_on_etb(self) -> None:
        """ETB trigger discards two cards after drawing."""
        game = create_game()
        p1 = game.players[0]

        jadzi = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)

        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        hand_cards = [CardImpl(name=f"Hand {i}", owner=p1) for i in range(3)]
        set_board_state(game, 0, hand=hand_cards, battlefield=[jadzi])
        for card in lib_cards:
            game.get_library(p1).append(card)

        jadzi.on_enter_battlefield(game)

        # Started with 3 in hand, drew 2 (=5), discarded 2 (=3)
        assert len(game.get_hand(p1)) == 3

    def test_discarded_cards_go_to_graveyard(self) -> None:
        """Discarded cards end up in the graveyard."""
        game = create_game()
        p1 = game.players[0]

        jadzi = JadziStewardOfFateOraclesGift(owner=p1, controller=p1)

        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[], battlefield=[jadzi], graveyard=[])
        for card in lib_cards:
            game.get_library(p1).append(card)

        jadzi.on_enter_battlefield(game)

        # Drew 2, then discarded 2 → graveyard should have 2
        assert len(game.get_graveyard(p1)) == 2
