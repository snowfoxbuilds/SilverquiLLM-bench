"""Audited tests for Leonin Skyhunter (FDN collector number 498) — flying."""

from __future__ import annotations

import pytest

from card_impl import LeoninSkyhunter

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestLeoninSkyhunterProperties:
    def test_is_creature(self) -> None:
        card = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert card.power == 2

    def test_toughness(self) -> None:
        card = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert card.toughness == 2

    def test_has_cat_subtype(self) -> None:
        card = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert "Cat" in card.subtypes

    def test_has_knight_subtype(self) -> None:
        card = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert "Knight" in card.subtypes


@pytest.mark.ability
class TestLeoninSkyhunterKeywords:
    def test_has_flying(self) -> None:
        card = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_only_flying(self) -> None:
        card = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert card.keywords == Keyword.FLYING


@pytest.mark.behavior
class TestLeoninSkyhunterBehavior:
    """Flying behavior: cannot be blocked by creatures without flying or reach."""

    def test_flying_cannot_be_blocked_by_ground_creature(self) -> None:
        """A ground creature cannot block a flyer."""
        from engine.combat import _can_block
        from engine.card import Creature

        flyer = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        ground = Creature(name="Ground Creature", owner=None)
        assert not _can_block(ground, flyer)

    def test_flying_can_be_blocked_by_flyer(self) -> None:
        """A creature with flying can block a flyer."""
        from engine.combat import _can_block

        flyer1 = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        flyer2 = LeoninSkyhunter(name="Leonin Skyhunter", owner=None)
        assert _can_block(flyer2, flyer1)
