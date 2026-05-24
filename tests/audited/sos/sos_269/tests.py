"""Audited tests for Swamp (SOS collector number 269).

Verifies basic land properties per card_spec.json.
"""

from __future__ import annotations

import pytest

from card_impl import Swamp

from benchmarks.sos.workspace.engine.card import Land
from benchmarks.sos.workspace.engine.types import CardType, Supertype


@pytest.mark.basic
class TestSwampBasicProperties:
    """Swamp basic property tests (trivial card: 5 tests)."""

    def test_is_land(self) -> None:
        """Swamp must be a Land subclass."""
        card = Swamp(name="Swamp", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        """Swamp must have the BASIC supertype."""
        card = Swamp(name="Swamp", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_land_subtype(self) -> None:
        """Swamp must have the 'Swamp' land subtype."""
        card = Swamp(name="Swamp", owner=None)
        assert "Swamp" in card.subtypes

    def test_name(self) -> None:
        """Swamp.name must be 'Swamp'."""
        card = Swamp(name="Swamp", owner=None)
        assert card.name == "Swamp"

    def test_enters_untapped(self) -> None:
        """Swamp enters the battlefield untapped."""
        card = Swamp(name="Swamp", owner=None)
        assert not card.is_tapped
