"""Tests for SOS 24 — Owlin Historian.

A 2/3 Bird Cleric with Flying for {2}{W}. ETB: surveil 1.
Whenever one or more cards leave your graveyard, gets +1/+1 until end of turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_24.card_impl import OwlinHistorian
from engine.card import Creature, CardImpl
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestOwlinHistorianProperties:
    """Static card data should match the SOS 24 spec."""

    def test_name(self) -> None:
        card = OwlinHistorian(owner=None)
        assert card.name == "Owlin Historian"

    def test_is_creature(self) -> None:
        card = OwlinHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost(self) -> None:
        card = OwlinHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}")

    def test_power_toughness(self) -> None:
        card = OwlinHistorian(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = OwlinHistorian(owner=None)
        assert Keyword.FLYING in card.keywords


class TestOwlinHistorianETBSurveil:
    """ETB trigger: surveil 1."""

    def test_etb_surveil_puts_card_in_graveyard(self) -> None:
        """Surveil 1 should allow putting top card into graveyard."""
        game = create_game()
        p1 = game.players[0]

        card = OwlinHistorian(owner=p1, controller=p1)
        card.card_types = {CardType.CREATURE}

        # Put a card on top of library
        top_card = CardImpl(owner=p1, name="Top Card")
        game.get_library(p1).add_to_top(top_card)

        graveyard_before = len(game.get_graveyard(p1).get_all())

        # Simulate ETB with surveil choosing graveyard
        card.on_enter_battlefield(game, surveil_choice="graveyard")

        graveyard_after = len(game.get_graveyard(p1).get_all())
        assert graveyard_after == graveyard_before + 1

    def test_etb_surveil_can_keep_on_top(self) -> None:
        """Surveil 1 should allow keeping card on top of library."""
        game = create_game()
        p1 = game.players[0]

        card = OwlinHistorian(owner=p1, controller=p1)
        card.card_types = {CardType.CREATURE}

        top_card = CardImpl(owner=p1, name="Top Card")
        game.get_library(p1).add_to_top(top_card)

        library_size_before = len(game.get_library(p1).get_all())

        card.on_enter_battlefield(game, surveil_choice="top")

        library_size_after = len(game.get_library(p1).get_all())
        assert library_size_after == library_size_before


class TestOwlinHistorianGraveyardLeave:
    """Whenever one or more cards leave graveyard, gets +1/+1 until end of turn."""

    def test_gets_plus_one_when_card_leaves_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        historian = OwlinHistorian(owner=p1, controller=p1)
        historian.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(historian)

        power_before = historian.get_power(game)
        toughness_before = historian.get_toughness(game)

        # Trigger the graveyard-leave ability
        historian.on_cards_leave_graveyard(game)

        assert historian.get_power(game) == power_before + 1
        assert historian.get_toughness(game) == toughness_before + 1

    def test_multiple_cards_leaving_triggers_once(self) -> None:
        """Multiple cards leaving at once = only one trigger (+1/+1 once)."""
        game = create_game()
        p1 = game.players[0]

        historian = OwlinHistorian(owner=p1, controller=p1)
        historian.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(historian)

        power_before = historian.get_power(game)

        # One event for multiple cards leaving
        historian.on_cards_leave_graveyard(game)

        assert historian.get_power(game) == power_before + 1

    def test_separate_leave_events_stack(self) -> None:
        """Two separate graveyard-leave events give +2/+2 total."""
        game = create_game()
        p1 = game.players[0]

        historian = OwlinHistorian(owner=p1, controller=p1)
        historian.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(historian)

        power_before = historian.get_power(game)

        historian.on_cards_leave_graveyard(game)
        historian.on_cards_leave_graveyard(game)

        assert historian.get_power(game) == power_before + 2
