"""Audited tests for FDN 222 — Ghalta, Primal Hunger."""

from __future__ import annotations

from card_impl import GhaltaPrimalHunger
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype
from tests.test_utils import create_game


class TestGhaltaBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = GhaltaPrimalHunger(owner=None)
        assert card.name == "Ghalta, Primal Hunger"

    def test_mana_cost(self) -> None:
        card = GhaltaPrimalHunger(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}{G}{G}")

    def test_power_toughness(self) -> None:
        card = GhaltaPrimalHunger(owner=None)
        assert card.base_power == 12
        assert card.base_toughness == 12

    def test_has_trample(self) -> None:
        card = GhaltaPrimalHunger(owner=None)
        assert Keyword.TRAMPLE & card.keywords

    def test_is_legendary(self) -> None:
        card = GhaltaPrimalHunger(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = GhaltaPrimalHunger(owner=None)
        assert "Elder" in card.subtypes
        assert "Dinosaur" in card.subtypes


class TestGhaltaCostReduction:
    """Cost reduction based on total power of creatures you control."""

    def test_reduces_by_total_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ghalta = GhaltaPrimalHunger(owner=p1, controller=p1)
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p1).add(c2)
        reduction = ghalta.cost_reduction(game)
        assert reduction == 5

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ghalta = GhaltaPrimalHunger(owner=p1, controller=p1)
        reduction = ghalta.cost_reduction(game)
        assert reduction == 0

