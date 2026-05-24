"""Audited tests for Mountain (SOS collector number 270).

Verifies basic land properties per card_spec.json.
"""

from __future__ import annotations

import pytest

from card_impl import Mountain

from benchmarks.sos.workspace.engine.card import Land
from benchmarks.sos.workspace.engine.types import CardType, Supertype


@pytest.mark.basic
class TestMountainBasicProperties:
    """Mountain basic property tests (trivial card: 5 tests)."""

    def test_is_land(self) -> None:
        """Mountain must be a Land subclass."""
        card = Mountain(name="Mountain", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        """Mountain must have the BASIC supertype."""
        card = Mountain(name="Mountain", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_land_subtype(self) -> None:
        """Mountain must have the 'Mountain' land subtype."""
        card = Mountain(name="Mountain", owner=None)
        assert "Mountain" in card.subtypes

    def test_name(self) -> None:
        """Mountain.name must be 'Mountain'."""
        card = Mountain(name="Mountain", owner=None)
        assert card.name == "Mountain"

    def test_enters_untapped(self) -> None:
        """Mountain enters the battlefield untapped."""
        card = Mountain(name="Mountain", owner=None)
        assert not card.is_tapped
