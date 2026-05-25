"""Audited tests for FDN 246 — Swiftblade Vindicator."""

from __future__ import annotations

from card_impl import SwiftbladeVindicator
from engine.card import Creature
from engine.types import Keyword, ManaCost
from test_utils import create_game


class TestSwiftbladeVindicatorBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert card.name == "Swiftblade Vindicator"

    def test_mana_cost(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert card.mana_cost == ManaCost.parse("{R}{W}")

    def test_power_toughness(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_is_creature(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert isinstance(card, Creature)

    def test_has_double_strike(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert Keyword.DOUBLE_STRIKE & card.keywords

    def test_has_vigilance(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert Keyword.VIGILANCE & card.keywords

    def test_has_trample(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert Keyword.TRAMPLE & card.keywords

    def test_subtypes(self) -> None:
        card = SwiftbladeVindicator(owner=None)
        assert "Human" in card.subtypes
        assert "Soldier" in card.subtypes

