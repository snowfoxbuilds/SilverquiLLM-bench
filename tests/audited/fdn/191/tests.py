"""Audited tests for Brazen Scourge (FDN collector number 191) — haste."""

from __future__ import annotations

import pytest

from card_impl import BrazenScourge

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestBrazenScourgeProperties:
    def test_is_creature(self) -> None:
        card = BrazenScourge(name="Brazen Scourge", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = BrazenScourge(name="Brazen Scourge", owner=None)
        assert card.power == 3

    def test_toughness(self) -> None:
        card = BrazenScourge(name="Brazen Scourge", owner=None)
        assert card.toughness == 3

    def test_has_gremlin_subtype(self) -> None:
        card = BrazenScourge(name="Brazen Scourge", owner=None)
        assert "Gremlin" in card.subtypes


@pytest.mark.ability
class TestBrazenScourgeKeywords:
    def test_has_haste(self) -> None:
        card = BrazenScourge(name="Brazen Scourge", owner=None)
        assert Keyword.HASTE in card.keywords

    def test_only_haste(self) -> None:
        card = BrazenScourge(name="Brazen Scourge", owner=None)
        assert card.keywords == Keyword.HASTE


@pytest.mark.behavior
class TestBrazenScourgeBehavior:
    """Haste behavior: can attack the turn it enters (no summoning sickness)."""

    def test_haste_allows_attack_with_summoning_sickness(self) -> None:
        """A creature with haste can attack even when summoning sick."""
        from engine.combat import _can_attack

        card = BrazenScourge(name="Brazen Scourge", owner=None)
        card.summoning_sick = True
        assert _can_attack(card)

    def test_non_haste_creature_cannot_attack_with_summoning_sickness(self) -> None:
        """A creature without haste cannot attack while summoning sick."""
        from engine.combat import _can_attack
        from engine.card import Creature

        vanilla = Creature(name="Vanilla", owner=None)
        vanilla.summoning_sick = True
        assert not _can_attack(vanilla)
