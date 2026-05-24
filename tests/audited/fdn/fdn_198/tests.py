"""Audited tests for FDN 198 — Flamewake Phoenix."""

from __future__ import annotations

from card_impl import FlamewakePhoenix
from engine.card import Creature
from engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFlamewakePhoenixBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert card.name == "Flamewake Phoenix"

    def test_mana_cost(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}{R}")

    def test_power_toughness(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_flying(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert Keyword.HASTE in card.keywords

    def test_subtypes(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert "Phoenix" in card.subtypes

    def test_must_attack(self) -> None:
        card = FlamewakePhoenix(owner=None)
        assert card.must_attack is True
