"""Audited tests for Stock Up (SOA collector number 24).

Verifies the Stock Up card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import StockUp

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestStockUpBasicProperties:
    """Stock Up basic property tests."""

    def test_is_sorcery(self) -> None:
        """Stock Up must be a Sorcery subclass."""
        card = StockUp(name="Stock Up", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """StockUp.name must be 'Stock Up'."""
        card = StockUp(name="Stock Up", owner=None)
        assert card.name == "Stock Up"

    def test_card_type(self) -> None:
        """Stock Up must have CardType.SORCERY."""
        card = StockUp(name="Stock Up", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Stock Up must have converted mana cost 3."""
        card = StockUp(name="Stock Up", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Stock Up must have colors ['U']."""
        card = StockUp(name="Stock Up", owner=None)
        for c in ["U"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestStockUpAbilities:
    """Stock Up ability tests — expected to fail against stubs."""

    def test_on_resolve_puts_card_in_hand(self) -> None:
        """Stock Up should put card(s) into hand on resolution.

        Oracle: Look at the top five cards of your library. Put two of them into your hand and the rest on the botto
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        for i in range(10):
            player.zones[Zone.LIBRARY].add(CardImpl(name=f"Lib{i}", owner=player))
        card = StockUp(name="Stock Up", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size increase. Before: {hand_before}, After: {hand_after}"
        )
