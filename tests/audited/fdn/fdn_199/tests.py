"""Audited tests for FDN 199 — Frenzied Goblin."""

from __future__ import annotations

from card_impl import FrenziedGoblin
from engine.card import Creature
from engine.types import ManaCost
from tests.test_utils import create_game


class TestFrenziedGoblinBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = FrenziedGoblin(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FrenziedGoblin(owner=None)
        assert card.name == "Frenzied Goblin"

    def test_mana_cost(self) -> None:
        card = FrenziedGoblin(owner=None)
        assert card.mana_cost == ManaCost.parse("{R}")

    def test_power_toughness(self) -> None:
        card = FrenziedGoblin(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = FrenziedGoblin(owner=None)
        assert "Goblin" in card.subtypes
        assert "Berserker" in card.subtypes
