"""Audited tests for Plains (FDN collector number 001).

Verifies the Plains card implementation through the ``card_impl`` module
injection mechanism provided by the FDN conftest.

Uses category markers per audited-test conventions:
- @pytest.mark.basic — fundamental card properties
- @pytest.mark.mana — mana ability tests
"""

from __future__ import annotations

import pytest

from card_impl import Plains

from engine.card import Land
from engine.types import Supertype


@pytest.mark.basic
class TestPlainsBasicProperties:
    """Basic property tests for the Plains card."""

    def test_plains_is_land(self) -> None:
        """Plains must be a Land subclass."""
        card = Plains(name="Plains", owner=None)
        assert isinstance(card, Land)

    def test_plains_has_basic_supertype(self) -> None:
        """Plains must have the BASIC supertype."""
        card = Plains(name="Plains", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_plains_has_plains_subtype(self) -> None:
        """Plains must have the 'Plains' land subtype."""
        card = Plains(name="Plains", owner=None)
        assert "Plains" in card.subtypes

    def test_plains_name(self) -> None:
        """Plains.name must be 'Plains'."""
        card = Plains(name="Plains", owner=None)
        assert card.name == "Plains"


@pytest.mark.mana
class TestPlainsManaAbility:
    """Mana ability tests for Plains."""

    def test_plains_taps_for_white_mana(self) -> None:
        """Plains must have a mana ability producing {W}."""
        card = Plains(name="Plains", owner=None)
        mana_abilities = card.get_mana_abilities()
        assert len(mana_abilities) > 0
        assert "{W}" in mana_abilities[0].description
