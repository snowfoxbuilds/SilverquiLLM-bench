"""Tests for SOS 88 — Leech Collector // Bloodletting.

{1}{B} Creature — Human Warlock 2/2 // {B} Sorcery
Whenever you gain life for the first time each turn, this creature becomes
prepared. (While it's prepared, you may cast a copy of its spell. Doing so
unprepares it.)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_88.card_impl import LeechCollector
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestLeechCollectorProperties:
    """Static card data should match the SOS 88 spec."""

    def test_is_creature(self) -> None:
        card = LeechCollector(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert LeechCollector(owner=None).name == "Leech Collector"

    def test_mana_cost(self) -> None:
        assert LeechCollector(owner=None).mana_cost == ManaCost.parse("{1}{B}")

    def test_power_and_toughness(self) -> None:
        card = LeechCollector(owner=None)
        assert card.power == 2
        assert card.toughness == 2


class TestLeechCollectorPrepared:
    """Prepared mechanic: becomes prepared on first life gain each turn."""

    def test_becomes_prepared_on_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]

        leech = LeechCollector(owner=p1, controller=p1)
        game.get_battlefield(p1).add(leech)

        assert leech.prepared is False

        # Simulate gaining life for the first time this turn
        leech.on_life_gained(game, p1, 1)

        assert leech.prepared is True

    def test_only_first_life_gain_triggers(self) -> None:
        """Second life gain in the same turn should not re-prepare."""
        game = create_game()
        p1 = game.players[0]

        leech = LeechCollector(owner=p1, controller=p1)
        game.get_battlefield(p1).add(leech)

        leech.on_life_gained(game, p1, 2)
        assert leech.prepared is True

        # Unprepare (simulate casting the spell copy)
        leech.prepared = False

        # Second life gain this turn should NOT re-prepare
        leech.on_life_gained(game, p1, 3)
        assert leech.prepared is False

    def test_starts_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        leech = LeechCollector(owner=p1, controller=p1)
        assert leech.prepared is False
