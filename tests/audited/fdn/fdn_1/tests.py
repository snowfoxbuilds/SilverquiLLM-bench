"""Audited tests for FDN 1 — Sire of Seven Deaths."""

from __future__ import annotations

from card_impl import SireOfSevenDeaths
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestSireOfSevenDeathsBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert card.name == "Sire of Seven Deaths"

    def test_mana_cost(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert card.mana_cost == ManaCost.parse("{7}")

    def test_power(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert card.base_power == 7

    def test_toughness(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert card.base_toughness == 7

    def test_eldrazi_subtype(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert "Eldrazi" in card.subtypes


class TestSireOfSevenDeathsKeywords:
    """All seven keywords present."""

    def test_has_first_strike(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords

    def test_has_vigilance(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_has_menace(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert Keyword.MENACE in card.keywords

    def test_has_trample(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_has_reach(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert Keyword.REACH in card.keywords

    def test_has_lifelink(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert Keyword.LIFELINK in card.keywords

    def test_has_ward(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert Keyword.WARD in card.keywords

    def test_ward_cost_is_7_life(self) -> None:
        card = SireOfSevenDeaths(owner=None)
        assert card.ward_cost == 7
