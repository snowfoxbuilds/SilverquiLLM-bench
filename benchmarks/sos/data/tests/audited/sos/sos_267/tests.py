"""Audited tests for Plains (SOS collector number 267).

Verifies basic land properties per card_spec.json.
"""

from __future__ import annotations

import pytest

from card_impl import Plains

from engine.card import Land
from engine.types import CardType, Supertype


@pytest.mark.basic
class TestPlainsBasicProperties:
    """Plains basic property tests (trivial card: 5 tests)."""

    def test_is_land(self) -> None:
        """Plains must be a Land subclass."""
        card = Plains(name="Plains", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        """Plains must have the BASIC supertype."""
        card = Plains(name="Plains", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_land_subtype(self) -> None:
        """Plains must have the 'Plains' land subtype."""
        card = Plains(name="Plains", owner=None)
        assert "Plains" in card.subtypes

    def test_name(self) -> None:
        """Plains.name must be 'Plains'."""
        card = Plains(name="Plains", owner=None)
        assert card.name == "Plains"

    def test_enters_untapped(self) -> None:
        """Plains enters the battlefield untapped."""
        card = Plains(name="Plains", owner=None)
        assert not card.is_tapped
