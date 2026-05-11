"""Audited tests for Magnigoth Sentry (FDN collector number 556) — reach."""

from __future__ import annotations

import pytest

from card_impl import MagnigothSentry

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestMagnigothSentryProperties:
    def test_is_creature(self) -> None:
        card = MagnigothSentry(name="Magnigoth Sentry", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = MagnigothSentry(name="Magnigoth Sentry", owner=None)
        assert card.power == 4

    def test_toughness(self) -> None:
        card = MagnigothSentry(name="Magnigoth Sentry", owner=None)
        assert card.toughness == 4

    def test_has_treefolk_subtype(self) -> None:
        card = MagnigothSentry(name="Magnigoth Sentry", owner=None)
        assert "Treefolk" in card.subtypes


@pytest.mark.ability
class TestMagnigothSentryKeywords:
    def test_has_reach(self) -> None:
        card = MagnigothSentry(name="Magnigoth Sentry", owner=None)
        assert Keyword.REACH in card.keywords

    def test_only_reach(self) -> None:
        card = MagnigothSentry(name="Magnigoth Sentry", owner=None)
        assert card.keywords == Keyword.REACH


@pytest.mark.behavior
class TestMagnigothSentryBehavior:
    """Reach behavior: can block creatures with flying."""

    def test_reach_can_block_flyer(self) -> None:
        """A creature with reach can block a creature with flying."""
        from engine.combat import _can_block
        from engine.card import Creature

        reacher = MagnigothSentry(name="Magnigoth Sentry", owner=None)
        flyer = Creature(name="Flyer", owner=None)
        flyer.keywords = Keyword.FLYING
        assert _can_block(reacher, flyer)
