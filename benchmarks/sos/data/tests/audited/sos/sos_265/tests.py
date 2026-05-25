"""Audited tests for Terramorphic Expanse (collector number 265).

Verifies the Terramorphic Expanse card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import TerramorphicExpanse

from engine.card import Land
from engine.types import CardType


@pytest.mark.basic
class TestTerramorphicExpanseBasicProperties:
    """Terramorphic Expanse basic property tests."""

    def test_is_land(self) -> None:
        """Terramorphic Expanse must be a Land subclass."""
        card = TerramorphicExpanse(name="Terramorphic Expanse", owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        """TerramorphicExpanse.name must be 'Terramorphic Expanse'."""
        card = TerramorphicExpanse(name="Terramorphic Expanse", owner=None)
        assert card.name == "Terramorphic Expanse"

    def test_card_type(self) -> None:
        """Terramorphic Expanse must have CardType.LAND."""
        card = TerramorphicExpanse(name="Terramorphic Expanse", owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        """Terramorphic Expanse is a land and has zero or no mana cost."""
        card = TerramorphicExpanse(name="Terramorphic Expanse", owner=None)
        mc = card.mana_cost
        assert mc is None or mc.cmc == 0


@pytest.mark.ability
class TestTerramorphicExpanseAbilities:
    """Terramorphic Expanse ability tests — expected to fail against stubs."""

    def test_has_activated_ability(self) -> None:
        """Terramorphic Expanse should have an activated ability.

        Oracle: {T}, Sacrifice this land: Search your library for a basic land card, put it onto the battlefield tap
        This test will fail against stubs (expected).
        """
        card = TerramorphicExpanse(name="Terramorphic Expanse", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) > 0, (
            f"Expected at least one activated ability on Terramorphic Expanse"
        )
