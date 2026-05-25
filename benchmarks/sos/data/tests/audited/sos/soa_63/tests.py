"""Audited tests for Deflecting Palm (SOA collector number 63).

Verifies the Deflecting Palm card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import DeflectingPalm

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDeflectingPalmBasicProperties:
    """Deflecting Palm basic property tests."""

    def test_is_instant(self) -> None:
        """Deflecting Palm must be a Instant subclass."""
        card = DeflectingPalm(name="Deflecting Palm", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """DeflectingPalm.name must be 'Deflecting Palm'."""
        card = DeflectingPalm(name="Deflecting Palm", owner=None)
        assert card.name == "Deflecting Palm"

    def test_card_type(self) -> None:
        """Deflecting Palm must have CardType.INSTANT."""
        card = DeflectingPalm(name="Deflecting Palm", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Deflecting Palm must have converted mana cost 2."""
        card = DeflectingPalm(name="Deflecting Palm", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Deflecting Palm must have colors ['R', 'W']."""
        card = DeflectingPalm(name="Deflecting Palm", owner=None)
        for c in ["R", "W"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestDeflectingPalmAbilities:
    """Deflecting Palm ability tests — expected to fail against stubs."""

    def test_on_resolve_sets_up_prevention(self) -> None:
        """Deflecting Palm should set up damage prevention.

        Oracle: The next time a source of your choice would deal damage to you this turn, prevent that damage. If da
        This test will fail against stubs (expected).
        """
        from test_utils import create_game

        game = create_game()
        player = game.players[0]
        card = DeflectingPalm(name="Deflecting Palm", owner=player)
        card.controller = player
        card.on_resolve(game)
        # A correct implementation should register a replacement effect
        assert len(game.replacement_manager.get_effects()) > 0, (
            f"Expected damage prevention effect registered after resolving Deflecting Palm"
        )
