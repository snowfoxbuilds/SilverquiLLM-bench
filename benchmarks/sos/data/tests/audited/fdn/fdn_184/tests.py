"""Audited tests for FDN 184 — Rune-Scarred Demon."""

from __future__ import annotations

from card_impl import RuneScarredDemon
from engine.card import CardImpl, Creature
from engine.types import Keyword, ManaCost, Zone
from test_utils import create_game


class TestRuneScarredDemonBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = RuneScarredDemon(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = RuneScarredDemon(owner=None)
        assert card.name == "Rune-Scarred Demon"

    def test_mana_cost(self) -> None:
        card = RuneScarredDemon(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{B}{B}")

    def test_power_toughness(self) -> None:
        card = RuneScarredDemon(owner=None)
        assert card.base_power == 6
        assert card.base_toughness == 6

    def test_has_flying(self) -> None:
        card = RuneScarredDemon(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = RuneScarredDemon(owner=None)
        assert "Demon" in card.subtypes


class TestRuneScarredDemonETB:
    """When this creature enters, search library for a card, put into hand, shuffle."""

    def test_searches_library_and_puts_card_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        demon = RuneScarredDemon(owner=p1, controller=p1)
        target_card = CardImpl(name="Prize", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(target_card)
        demon.on_resolve(game)
        assert game.get_hand(p1).contains(target_card)

    def test_no_error_on_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        demon = RuneScarredDemon(owner=p1, controller=p1)
        # Library is empty by default
        demon.on_resolve(game)
        # Should not raise
