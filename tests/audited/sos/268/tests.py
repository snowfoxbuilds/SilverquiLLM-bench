"""Audited tests for Island (SOS collector number 268).

Verifies basic land properties per card_spec.json.
"""

from __future__ import annotations

import pytest

from card_impl import Island

from engine.card import Land
from engine.types import CardType, Supertype


@pytest.mark.basic
class TestIslandBasicProperties:
    """Island basic property tests (trivial card: 5 tests)."""

    def test_is_land(self) -> None:
        """Island must be a Land subclass."""
        card = Island(name="Island", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        """Island must have the BASIC supertype."""
        card = Island(name="Island", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_land_subtype(self) -> None:
        """Island must have the 'Island' land subtype."""
        card = Island(name="Island", owner=None)
        assert "Island" in card.subtypes

    def test_name(self) -> None:
        """Island.name must be 'Island'."""
        card = Island(name="Island", owner=None)
        assert card.name == "Island"

    def test_enters_untapped(self) -> None:
        """Island enters the battlefield untapped."""
        card = Island(name="Island", owner=None)
        assert not card.is_tapped
