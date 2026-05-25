"""Audited tests for FDN 171 — Diregraf Ghoul."""

from __future__ import annotations

from card_impl import DiregrafGhoul
from engine.card import Creature
from engine.types import ManaCost
from test_utils import create_game


class TestDiregrafGhoulBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = DiregrafGhoul(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = DiregrafGhoul(owner=None)
        assert card.name == "Diregraf Ghoul"

    def test_mana_cost(self) -> None:
        card = DiregrafGhoul(owner=None)
        assert card.mana_cost == ManaCost.parse("{B}")

    def test_power_toughness(self) -> None:
        card = DiregrafGhoul(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = DiregrafGhoul(owner=None)
        assert "Zombie" in card.subtypes


class TestDiregrafGhoulEntersTapped:
    """This creature enters tapped."""

    def test_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ghoul = DiregrafGhoul(owner=p1, controller=p1)
        ghoul.on_resolve(game)
        assert ghoul.is_tapped is True
