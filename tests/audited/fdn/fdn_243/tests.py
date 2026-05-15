"""Audited tests for FDN 243 — Muldrotha, the Gravetide."""

from __future__ import annotations

from card_impl import MuldrothaTheGravetide
from engine.card import Creature
from engine.types import ManaCost, Supertype
from tests.test_utils import create_game


class TestMuldrothaBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = MuldrothaTheGravetide(owner=None)
        assert card.name == "Muldrotha, the Gravetide"

    def test_mana_cost(self) -> None:
        card = MuldrothaTheGravetide(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}{G}{U}")

    def test_power_toughness(self) -> None:
        card = MuldrothaTheGravetide(owner=None)
        assert card.base_power == 6
        assert card.base_toughness == 6

    def test_is_legendary(self) -> None:
        card = MuldrothaTheGravetide(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = MuldrothaTheGravetide(owner=None)
        assert "Elemental" in card.subtypes
        assert "Avatar" in card.subtypes


class TestMuldrothaAbility:
    """Graveyard casting permission marker."""

    def test_registers_graveyard_casting_marker(self) -> None:
        game = create_game()
        p1 = game.players[0]
        muldrotha = MuldrothaTheGravetide(owner=p1, controller=p1)
        game.get_battlefield(p1).add(muldrotha)
        muldrotha.register_triggers(game)
        assert muldrotha._allows_graveyard_casting is True

