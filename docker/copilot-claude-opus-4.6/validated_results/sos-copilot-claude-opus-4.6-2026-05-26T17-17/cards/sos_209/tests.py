"""Tests for SOS 209 — Pest Mascot.

Creature — Pest Ape (2/3) {1}{B}{G}
- Trample
- Whenever you gain life, put a +1/+1 counter on this creature.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_209.card_impl import PestMascot
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestPestMascotProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = PestMascot(owner=None)
        assert card.name == "Pest Mascot"

    def test_mana_cost(self) -> None:
        card = PestMascot(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")

    def test_power_toughness(self) -> None:
        card = PestMascot(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_is_creature(self) -> None:
        card = PestMascot(owner=None)
        assert isinstance(card, Creature)

    def test_has_trample(self) -> None:
        card = PestMascot(owner=None)
        assert Keyword.TRAMPLE in card.keywords


class TestPestMascotLifeGainTrigger:
    """Whenever you gain life, put a +1/+1 counter on this creature."""

    def test_gaining_life_adds_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        card.on_life_gained(game, amount=3)

        assert card.plus_one_counters == 1

    def test_multiple_life_gain_events_add_multiple_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        card.on_life_gained(game, amount=2)
        card.on_life_gained(game, amount=5)
        card.on_life_gained(game, amount=1)

        assert card.plus_one_counters == 3

    def test_counter_increases_power_and_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        card.on_life_gained(game, amount=4)

        assert card.power == 3
        assert card.toughness == 4

    def test_opponent_gaining_life_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = PestMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Opponent life gain should not trigger
        card.on_opponent_life_gained(game, amount=5)

        assert card.plus_one_counters == 0

    def test_one_counter_per_event_regardless_of_amount(self) -> None:
        """Each life gain event adds exactly one counter, not one per life point."""
        game = create_game()
        p1 = game.players[0]
        card = PestMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        card.on_life_gained(game, amount=100)

        assert card.plus_one_counters == 1
