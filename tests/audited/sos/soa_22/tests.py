"""Audited tests for Sleight of Hand (SOA collector number 22).

Verifies the Sleight of Hand card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SleightOfHand

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSleightOfHandBasicProperties:
    """Sleight of Hand basic property tests."""

    def test_is_sorcery(self) -> None:
        """Sleight of Hand must be a Sorcery subclass."""
        card = SleightOfHand(name="Sleight of Hand", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """SleightOfHand.name must be 'Sleight of Hand'."""
        card = SleightOfHand(name="Sleight of Hand", owner=None)
        assert card.name == "Sleight of Hand"

    def test_card_type(self) -> None:
        """Sleight of Hand must have CardType.SORCERY."""
        card = SleightOfHand(name="Sleight of Hand", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Sleight of Hand must have converted mana cost 1."""
        card = SleightOfHand(name="Sleight of Hand", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Sleight of Hand must have colors ['U']."""
        card = SleightOfHand(name="Sleight of Hand", owner=None)
        for c in ["U"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestSleightOfHandAbilities:
    """Sleight of Hand ability tests — expected to fail against stubs."""

    def test_on_resolve_puts_card_in_hand(self) -> None:
        """Sleight of Hand should put card(s) into hand on resolution.

        Oracle: Look at the top two cards of your library. Put one of them into your hand and the other on the botto
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        for i in range(10):
            player.zones[Zone.LIBRARY].add(CardImpl(name=f"Lib{i}", owner=player))
        card = SleightOfHand(name="Sleight of Hand", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size increase. Before: {hand_before}, After: {hand_after}"
        )
