"""Audited tests for Hop to It (SOA collector number 6).

Verifies the Hop to It card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import HopToIt

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestHopToItBasicProperties:
    """Hop to It basic property tests."""

    def test_is_sorcery(self) -> None:
        """Hop to It must be a Sorcery subclass."""
        card = HopToIt(name="Hop to It", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """HopToIt.name must be 'Hop to It'."""
        card = HopToIt(name="Hop to It", owner=None)
        assert card.name == "Hop to It"

    def test_card_type(self) -> None:
        """Hop to It must have CardType.SORCERY."""
        card = HopToIt(name="Hop to It", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Hop to It must have converted mana cost 3."""
        card = HopToIt(name="Hop to It", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Hop to It must have colors ['W']."""
        card = HopToIt(name="Hop to It", owner=None)
        for c in ["W"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestHopToItAbilities:
    """Hop to It ability tests — expected to fail against stubs."""

    def test_on_resolve_creates_tokens(self) -> None:
        """Hop to It should create token(s) on resolution.

        Oracle: Create three 1/1 white Rabbit creature tokens.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = HopToIt(name="Hop to It", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Expected tokens on battlefield after resolving Hop to It. "
            f"Before: {bf_before}, After: {bf_after}"
        )
