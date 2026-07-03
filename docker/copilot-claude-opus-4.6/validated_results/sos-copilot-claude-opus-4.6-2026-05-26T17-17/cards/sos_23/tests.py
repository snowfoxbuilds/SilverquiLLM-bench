"""Tests for SOS 23 — Joined Researchers // Secret Rendezvous.

A 2/2 creature with first strike for {1}{W}. At the beginning of each
end step, if an opponent has more cards in hand than you, this creature
becomes prepared.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_23.card_impl import JoinedResearchersSecretRendezvous
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestJoinedResearchersProperties:
    """Static card data should match the SOS 23 spec."""

    def test_name(self) -> None:
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert card.name == "Joined Researchers // Secret Rendezvous"

    def test_is_creature(self) -> None:
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost(self) -> None:
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_first_strike(self) -> None:
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords


class TestJoinedResearchersPrepared:
    """End step trigger: becomes prepared if opponent has more cards in hand."""

    def test_becomes_prepared_when_opponent_has_more_cards(self) -> None:
        """If opponent's hand size > controller's, creature becomes prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)
        card.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(card)

        # Give opponent more cards in hand
        from engine.card import CardImpl
        set_board_state(game, 0, hand=[])
        set_board_state(game, 1, hand=[CardImpl(owner=p2), CardImpl(owner=p2), CardImpl(owner=p2)])

        # Simulate end step trigger
        card.on_end_step(game)

        assert card.is_prepared is True

    def test_does_not_become_prepared_when_hands_equal(self) -> None:
        """If hand sizes are equal, creature does NOT become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)
        card.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(card)

        # Equal hand sizes
        from engine.card import CardImpl
        set_board_state(game, 0, hand=[CardImpl(owner=p1)])
        set_board_state(game, 1, hand=[CardImpl(owner=p2)])

        card.on_end_step(game)

        assert card.is_prepared is False

    def test_does_not_become_prepared_when_controller_has_more(self) -> None:
        """If controller has more cards than opponent, not prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = JoinedResearchersSecretRendezvous(owner=p1, controller=p1)
        card.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(card)

        from engine.card import CardImpl
        set_board_state(game, 0, hand=[CardImpl(owner=p1), CardImpl(owner=p1), CardImpl(owner=p1)])
        set_board_state(game, 1, hand=[CardImpl(owner=p2)])

        card.on_end_step(game)

        assert card.is_prepared is False

    def test_prepared_starts_false(self) -> None:
        """Card should not start prepared."""
        card = JoinedResearchersSecretRendezvous(owner=None)
        assert card.is_prepared is False
