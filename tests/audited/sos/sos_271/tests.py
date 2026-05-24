"""Audited tests for Forest (SOS collector number 271).

Verifies basic land properties per card_spec.json.
"""

from __future__ import annotations

import pytest

from card_impl import Forest

from benchmarks.sos.workspace.engine.card import Land
from benchmarks.sos.workspace.engine.types import CardType, Supertype


@pytest.mark.basic
class TestForestBasicProperties:
    """Forest basic property tests (trivial card: 5 tests)."""

    def test_is_land(self) -> None:
        """Forest must be a Land subclass."""
        card = Forest(name="Forest", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        """Forest must have the BASIC supertype."""
        card = Forest(name="Forest", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_land_subtype(self) -> None:
        """Forest must have the 'Forest' land subtype."""
        card = Forest(name="Forest", owner=None)
        assert "Forest" in card.subtypes

    def test_name(self) -> None:
        """Forest.name must be 'Forest'."""
        card = Forest(name="Forest", owner=None)
        assert card.name == "Forest"

    def test_enters_untapped(self) -> None:
        """Forest enters the battlefield untapped."""
        card = Forest(name="Forest", owner=None)
        assert not card.is_tapped
