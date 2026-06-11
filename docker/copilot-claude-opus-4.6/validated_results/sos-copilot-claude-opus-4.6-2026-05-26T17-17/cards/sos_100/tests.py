"""Tests for SOS 100 — Send in the Pest.

{1}{B} Sorcery
Each opponent discards a card. You create a 1/1 black and green Pest creature
token with "Whenever this token attacks, you gain 1 life."
"""

from __future__ import annotations

import pytest

from cards.sos.sos_100.card_impl import SendInThePest
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSendInThePestProperties:
    """Static card data should match the SOS 100 spec."""

    def test_is_sorcery(self) -> None:
        card = SendInThePest(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = SendInThePest(owner=None)
        assert card.name == "Send in the Pest"

    def test_mana_cost(self) -> None:
        card = SendInThePest(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")


class TestSendInThePestResolution:
    """on_resolve causes opponents to discard and creates a Pest token."""

    def test_opponent_discards_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        hand_card = Creature(name="Victim", owner=p2, base_power=1, base_toughness=1)
        set_board_state(game, 1, hand=[hand_card])

        spell = SendInThePest(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Opponent should have discarded
        assert len(game.get_hand(p2).get_all()) == 0

    def test_creates_pest_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 1, hand=[])

        spell = SendInThePest(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Should have created a token on p1's battlefield
        bf = game.get_battlefield(p1).get_all()
        pests = [c for c in bf if getattr(c, 'name', '') == "Pest" or "Pest" in getattr(c, 'subtypes', set())]
        assert len(pests) == 1

    def test_pest_token_is_one_one(self) -> None:
        game = create_game()
        p1 = game.players[0]

        set_board_state(game, 1, hand=[])

        spell = SendInThePest(owner=p1, controller=p1)
        spell.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        pests = [c for c in bf if getattr(c, 'name', '') == "Pest" or "Pest" in getattr(c, 'subtypes', set())]
        assert len(pests) == 1
        pest = pests[0]
        assert pest.power == 1
        assert pest.toughness == 1

    def test_opponent_with_empty_hand_still_allows_resolution(self) -> None:
        """If opponent has no cards, spell still resolves and creates token."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 1, hand=[])

        spell = SendInThePest(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Token should still be created
        bf = game.get_battlefield(p1).get_all()
        assert len(bf) >= 1
