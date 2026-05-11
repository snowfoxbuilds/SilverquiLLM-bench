"""Audited tests for Skyraker Giant (FDN collector number 547) — reach."""

from __future__ import annotations

import pytest

from card_impl import SkyrakerGiant

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestSkyrakerGiantProperties:
    def test_is_creature(self) -> None:
        card = SkyrakerGiant(name="Skyraker Giant", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = SkyrakerGiant(name="Skyraker Giant", owner=None)
        assert card.power == 4

    def test_toughness(self) -> None:
        card = SkyrakerGiant(name="Skyraker Giant", owner=None)
        assert card.toughness == 3

    def test_has_giant_subtype(self) -> None:
        card = SkyrakerGiant(name="Skyraker Giant", owner=None)
        assert "Giant" in card.subtypes


@pytest.mark.ability
class TestSkyrakerGiantKeywords:
    def test_has_reach(self) -> None:
        card = SkyrakerGiant(name="Skyraker Giant", owner=None)
        assert Keyword.REACH in card.keywords

    def test_only_reach(self) -> None:
        card = SkyrakerGiant(name="Skyraker Giant", owner=None)
        assert card.keywords == Keyword.REACH


@pytest.mark.behavior
class TestSkyrakerGiantBehavior:
    """Reach behavior: can block creatures with flying."""

    def test_reach_can_block_flyer(self) -> None:
        """A creature with reach can block a creature with flying."""
        from engine.combat import _can_block
        from engine.card import Creature

        reacher = SkyrakerGiant(name="Skyraker Giant", owner=None)
        flyer = Creature(name="Flyer", owner=None)
        flyer.keywords = Keyword.FLYING
        assert _can_block(reacher, flyer)

    def test_ground_creature_cannot_block_flyer(self) -> None:
        """A ground creature (no reach/flying) cannot block a flyer."""
        from engine.combat import _can_block
        from engine.card import Creature

        ground = Creature(name="Ground", owner=None)
        flyer = Creature(name="Flyer", owner=None)
        flyer.keywords = Keyword.FLYING
        assert not _can_block(ground, flyer)
